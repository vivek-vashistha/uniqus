
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASC 606 Contract Analyzer with OpenAI Responses API + Vector Store (File Search)
-------------------------------------------------------------------------------
- Isolation: One vector store per contract_id (prevents cross-contract mixing)
- Flow: Heuristics first -> Only-fill-Unknowns via RAG (Responses + File Search)
- Outputs: Excel (Step 1..5), JSON (answers + citations)

Quick start
-----------
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...

# 1) Ingest a contract file (PDF/DOCX/TXT) into its own vector store
python asc606_rag_filler.py ingest --contract_id C-001 --files "./contracts/ContractA.pdf"

# 2) Analyze it: fills steps 1..5 from heuristics + RAG fallback
python asc606_rag_filler.py analyze --contract_id C-001 --out_xlsx "ASC606_C001.xlsx" --out_json "ASC606_C001.json"

Optional:
- Add more files to the same contract_id with another `ingest` call.
- Point `--model` to your preferred OpenAI model (e.g., gpt-4.1, o3-mini, gpt-4o-mini).

Notes
-----
- The script uses OpenAI's Responses API with the File Search tool. The vector store is attached per request to
  guarantee isolation. See inline comments where the vector_store_id is passed.
- PDF parsing for heuristics does not require OpenAI; we just use PyPDF2/python-docx if needed.
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Local caches
VECTOR_MAP_PATH = ".vector_store_map.json"   # contract_id -> vector_store_id

# Load environment variables
load_dotenv()

# Environment variables
API_KEY = os.getenv("DIRECT_OPENAI_API_KEY")

# ------------------------
# OpenAI client
# ------------------------
try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None

def get_client():
    if not API_KEY:
        print("❌ DIRECT_OPENAI_API_KEY is missing in .env", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=API_KEY)

# ------------------------
# Simple text extraction (for heuristics)
# ------------------------
def _safe_import_pypdf2():
    try:
        import PyPDF2
        return PyPDF2
    except Exception:
        return None

def _safe_import_docx():
    try:
        import docx
        return docx
    except Exception:
        return None

def extract_text_local(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf_text(path)
    elif ext in [".docx"]:
        return _extract_docx_text(path)
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

def _extract_pdf_text(path: str) -> str:
    PyPDF2 = _safe_import_pypdf2()
    if PyPDF2 is None:
        return ""
    out = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for p in reader.pages:
            try:
                out.append(p.extract_text() or "")
            except Exception:
                out.append("")
    return "\n\n".join(out)

def _extract_docx_text(path: str) -> str:
    docx = _safe_import_docx()
    if docx is None:
        return ""
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

# ------------------------
# Heuristic analyzers (same core as the earlier script)
# ------------------------
@dataclass
class Finding:
    answer: str
    rationale: str
    citations: List[Dict[str,str]] = field(default_factory=list)  # [{"doc":"", "page":"", "quote":""}]

@dataclass
class StepOutputs:
    step1: Dict[str, Finding] = field(default_factory=dict)
    step2: Dict[str, Any] = field(default_factory=dict)
    step3: Dict[str, Any] = field(default_factory=dict)
    step4: Dict[str, Any] = field(default_factory=dict)
    step5: Dict[str, Any] = field(default_factory=dict)

def _find_snippets(text: str, keyword: str, window: int = 240) -> List[str]:
    out = []
    for m in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        out.append(text[start:end].strip())
    return out[:5]

def _first_match(text: str, patterns: List[str]) -> Optional[re.Match]:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE|re.DOTALL)
        if m:
            return m
    return None

def _money_mentions(text: str) -> List[str]:
    return re.findall(r'(\$[\s]*[0-9][0-9,]*\.?[0-9]*|\bUSD\s*[0-9][0-9,]*\.?[0-9]*)', text, flags=re.IGNORECASE)

def analyze_step1_heur(text: str) -> Dict[str, Finding]:
    out: Dict[str, Finding] = {}

    evidence = _first_match(text, [r'\bMASTER\b.*\bAGREEMENT\b', r'\bWORK ORDER\b', r'\bAGREEMENT\b.*\bbetween\b'])
    out["agreement_exists"] = Finding(
        "Yes" if evidence else "Unknown",
        f"Evidence: {'found' if evidence else 'not found'} for agreement terms (e.g., 'Agreement', 'Work Order')."
    )

    sig = _first_match(text, [r'\bEffective Date\b.*?[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}', r'\bSigned\b', r'\bSignature\b'])
    out["approved_committed"] = Finding(
        "Yes" if sig else "Unknown",
        "Looked for 'Effective Date', 'Signed', 'Signature' to infer commitment."
    )

    rights = _first_match(text, [r'\bright[s]?\b.*\bservices?\b', r'\bdeliverables?\b', r'\bScope of Work\b', r'\bServices shall\b'])
    out["rights_identified"] = Finding(
        "Yes" if rights else "Unknown",
        "Searched for 'deliverables', 'scope of work', 'services shall'."
    )

    pay = _first_match(text, [r'\bInvoice[s]?\b.*?\b(?:within|due)\b.*?\b(?:days|day)\b', r'\bPayment Terms\b', r'\bNet\s*\d+\b'])
    out["payment_terms_identified"] = Finding(
        "Yes" if pay else "Unknown",
        "Searched for 'Invoice', 'Payment Terms', 'Net XX days'."
    )

    monies = _money_mentions(text)
    out["commercial_substance"] = Finding(
        "Yes" if monies else "Unknown",
        f"Detected monetary terms: {', '.join(monies[:5]) if monies else 'none'}."
    )

    credit_clues = bool(_first_match(text, [r'\binterest on overdue\b', r'\bdispute\b.*\bwithhold\b', r'\bcredit\b']))
    out["collectibility_probable"] = Finding(
        "Yes" if credit_clues or monies else "Unknown",
        "Assessed based on presence of fees and payment/credit protection language."
    )

    dates = re.findall(r'(?:Effective Date|Date[:\s])\s*[:\-]?\s*([A-Za-z]{3,9}\s*\d{1,2},\s*\d{4}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})', text, flags=re.IGNORECASE)
    out["multiple_contracts_near_time"] = Finding(
        "Unknown",
        f"Found dates: {dates[:5]} (manual check needed for ±3 months)."
    )

    package = _first_match(text, [r'\bpursuant to\b.*\bMaster\b', r'\bunder\b.*\bMaster.*Agreement\b', r'\bWork Order\b.*\bpursuant\b'])
    out["negotiated_as_package"] = Finding(
        "Yes" if package else "Unknown",
        "Looked for 'pursuant to Master Agreement' / 'under MSA'."
    )

    out["combine_contracts"] = Finding(
        "Unknown",
        "Requires judgment on single commercial objective, interdependent pricing."
    )

    conclusion_yes = all(v.answer in ["Yes", "Unknown"] for k, v in out.items() if k in [
        "agreement_exists", "approved_committed", "rights_identified", "payment_terms_identified", "commercial_substance", "collectibility_probable"
    ]) and out["agreement_exists"].answer == "Yes"
    out["conclusion_contract_exists"] = Finding(
        "Yes" if conclusion_yes else "Unknown",
        "Based on presence of agreement, rights, payment terms, and monetary substance."
    )
    return out

def _extract_promised_services(text: str) -> List[str]:
    services = set()
    blocks = re.split(r'\n{2,}', text)
    for b in blocks:
        headerish = re.match(r'\s*(?:Services?|Deliverables?|Scope|Work Order|Exhibit A)\b.*', b, re.IGNORECASE)
        if headerish:
            for line in b.splitlines():
                if re.search(r'^\s*[\-\u2022\*]\s+.+', line) or re.search(r'\bservices?\b', line, re.IGNORECASE):
                    ln = re.sub(r'^\s*[\-\u2022\*]\s*', '', line).strip()
                    if 5 <= len(ln) <= 200:
                        services.add(ln)
    for m in re.finditer(r'\b(?:shall|will)\s+provide\s+([^\.]{10,200})\.', text, re.IGNORECASE):
        segment = m.group(1).strip()
        services.add(segment)
    return list(services)[:12]

def analyze_step2_heur(text: str) -> Dict[str, Any]:
    services = _extract_promised_services(text)
    rows = []
    for i, s in enumerate(services, start=1):
        benefit = "Yes" if len(s.split()) >= 3 else "Unknown"
        separately_identifiable = "Yes" if not re.search(r'\bintegrated|combined|dependent|interdependent|highly integrated\b', s, re.IGNORECASE) else "No"
        distinct = "Yes" if benefit == "Yes" and separately_identifiable == "Yes" else "Unknown"
        rationale = "Heuristic: treat as distinct if customer can benefit on its own and promise not highly integrated."
        rows.append({
            "promised_service": s,
            "customer_can_benefit": benefit,
            "separately_identifiable": separately_identifiable,
            "distinct": distinct,
            "rationale": rationale,
            "po_number": i if distinct == "Yes" else ""
        })
    meta = {
        "has_setup_only": "Unknown",
        "has_material_rights": "Unknown",
        "series_treated_as_one": "Unknown"
    }
    return {"rows": rows, "meta": meta}

def analyze_step3_heur(text: str) -> Dict[str, Any]:
    fixed = []
    variable = []
    for snip in _find_snippets(text, "$"):
        fixed.append(snip)
    for kw in ["bonus", "penalty", "rebate", "incentive", "price adjustment", "liquidated damages"]:
        variable.extend(_find_snippets(text, kw))
    financing = "Yes" if re.search(r'\bfinancing component\b|\bdeferred payment\b|\binstallments?\b', text, re.IGNORECASE) else "Unknown"
    payable_to_customer = "Yes" if re.search(r'\b(payable to customer|customer incentive|credit to customer)\b', text, re.IGNORECASE) else "Unknown"
    total_hint = ", ".join(sorted(set(_money_mentions(text)))[:8])
    return {
        "fixed_consideration_examples": fixed[:5],
        "variable_consideration_examples": variable[:5],
        "non_cash": "Unknown",
        "significant_financing_component": financing,
        "consideration_payable_to_customer": payable_to_customer,
        "total_transaction_price_hint_values": total_hint
    }

def analyze_step4_heur(step2: Dict[str, Any], step3: Dict[str, Any]) -> Dict[str, Any]:
    pos = [r for r in step2.get("rows", []) if r.get("distinct") == "Yes"]
    alloc_rows = []
    for i, r in enumerate(pos, start=1):
        alloc_rows.append({
            "po_number": r.get("po_number"),
            "description": r.get("promised_service")[:120],
            "observable_ssp": "Unknown",
            "ssp_value": "",
            "allocation_method": "Relative SSP (placeholder)",
            "allocated_transaction_price": ""
        })
    return {"rows": alloc_rows, "note": f"{len(pos)} distinct POs detected; add SSPs and totals to complete allocation."}

def analyze_step5_heur(step2: Dict[str, Any], text: str) -> Dict[str, Any]:
    rows = []
    over_time_cues = bool(re.search(r'\bover time\b|monthly|quarterly|annual|term of the agreement|service levels?', text, re.IGNORECASE))
    acceptance_cues = _find_snippets(text, "acceptance")
    for r in step2.get("rows", []):
        po = r.get("po_number")
        if not po:
            continue
        timing = "Over Time" if over_time_cues else "Unknown"
        rationale = "Heuristic: recurring/term-based services typically recognized over time (ASC 606-10-25-27)." if timing=="Over Time" else "Insufficient cues."
        method = "Input (time & materials or cost-to-cost) – placeholder"
        rows.append({
            "po_number": po,
            "satisfied_when": timing,
            "rationale": rationale,
            "progress_method": method,
            "milestones_acceptance": "; ".join(acceptance_cues[:2]) if acceptance_cues else "",
            "timing_pattern": "Straight-line over term (placeholder)" if timing=="Over Time" else ""
        })
    return {"rows": rows}

# ------------------------
# Vector store management
# ------------------------
def load_vector_map() -> Dict[str, str]:
    if not os.path.exists(VECTOR_MAP_PATH):
        return {}
    with open(VECTOR_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_vector_map(m: Dict[str, str]) -> None:
    with open(VECTOR_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2)

def ensure_vector_store(client: "OpenAI", contract_id: str) -> str:
    m = load_vector_map()
    if contract_id in m:
        return m[contract_id]
    # Create a new vector store
    vs = client.vector_stores.create(name=f"asc606_{contract_id}")
    m[contract_id] = vs.id
    save_vector_map(m)
    return vs.id

def add_files_to_store(client: "OpenAI", vector_store_id: str, paths: List[str]) -> None:
    file_streams = []
    for p in paths:
        file_streams.append(open(p, "rb"))
    try:
        # Batch upload and poll until indexed
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store_id,
            files=file_streams
        )
    finally:
        for fs in file_streams:
            try:
                fs.close()
            except Exception:
                pass

# ------------------------
# RAG question answerer
# ------------------------
def ask_rag(client: "OpenAI", model: str, vector_store_id: str, question: str, contract_id: str) -> Dict[str, Any]:
    """
    Calls the OpenAI Responses API with File Search tool, restricted to the given vector_store_id.
    We instruct the model to return STRICT JSON: {"answer": "...", "rationale": "...", "citations":[{"doc":"","page":"","quote":""}, ...]}
    """
    system_msg = (
        "You are an ASC 606 accounting assistant. Answer ONLY using the attached file search results. "
        "If evidence is insufficient, return answer='Unknown' with rationale explaining what's missing. "
        "Always include citations (doc name + page + short quote) from the retrieved context. "
        "You MUST return ONLY valid JSON in the exact format specified in the user prompt."
    )

    prompt = f"""Question: {question}

Return JSON with this schema exactly:
{{
  "answer": "Yes|No|Unknown|<value>",
  "rationale": "<concise reasoning from retrieved text>",
  "citations": [{{"doc":"<document name>","page":"<page or section>","quote":"<<=120 chars supporting quote>"}}, ...]
}}"""

    # NOTE: The Responses API supports `tools=[{"type":"file_search"}]` and attaching vector stores to the request.
    # Depending on SDK version, the vector store attachment may be passed via tool resources or file_search params.
    # We use the "tool_resources" param which is the current SDK pattern.
    resp = client.responses.create(
        model=model,
        input=[
            {"role":"system","content":system_msg},
            {"role":"user","content":prompt}
        ],
        tools=[{
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id]
                }],
        metadata={"contract_id": contract_id}
    )

    try:
        # Try to get content from the response
        content = resp.output_text.strip()
    except Exception:
        # Fallback: try alternative access patterns
        try:
            content = resp.output[0].content[0].text.strip()
        except Exception:
            content = ""

    # Try to parse as JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        # If JSON parsing fails, try to extract JSON from the response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # If all parsing fails, return error response
        return {
            "answer": "Unknown",
            "rationale": f"Failed to parse model JSON: {str(e)}. Raw response: {content[:200]}...",
            "citations": []
        }

# ------------------------
# Step controller: heuristics -> only-fill-unknowns via RAG
# ------------------------
def step_questions() -> Dict[str, List[Dict[str, Any]]]:
    """
    Define the canonical questions we will ask. Keys are step names; values are list of dicts:
      - key: internal key
      - question: textual question for RAG
      - type: "yn" or "text" (controls expected answer style)
    """
    return {
        "step1":[
            {"key":"agreement_exists", "type":"yn", "question":"Is there an agreement (MSA/WO) between the parties?"},
            {"key":"approved_committed", "type":"yn", "question":"Is the contract approved and are the parties committed?"},
            {"key":"rights_identified", "type":"yn", "question":"Are parties' rights and services to be transferred identifiable?"},
            {"key":"payment_terms_identified", "type":"yn", "question":"Are the payment terms identifiable (e.g., invoice timing, Net terms)?"},
            {"key":"commercial_substance", "type":"yn", "question":"Does the contract have commercial substance (changes to cash flows)?"},
            {"key":"collectibility_probable", "type":"yn", "question":"Is collection of consideration probable (ASC 606-10-25-1(e))?"},
            {"key":"multiple_contracts_near_time", "type":"yn", "question":"Were any other contracts entered at or near the same time (~3 months) with the same or related parties?"},
            {"key":"negotiated_as_package", "type":"yn", "question":"Were contracts negotiated as a package with a single commercial objective?"},
            {"key":"combine_contracts", "type":"yn", "question":"Should the contracts be combined for accounting purposes?"},
            {"key":"conclusion_contract_exists", "type":"yn", "question":"Conclusion: Does a contract exist per ASC 606-10-25-1(a–e)?"}
        ],
        "step2":[
            {"key":"promised_services", "type":"text", "question":"List each promised good/service and assess distinctness with brief rationale."}
        ],
        "step3":[
            {"key":"transaction_price", "type":"text", "question":"Summarize transaction price: fixed consideration, variable components, any significant financing, consideration payable to customer, and non-cash consideration."}
        ],
        "step4":[
            {"key":"allocation", "type":"text", "question":"Allocate the transaction price across performance obligations using SSP (state SSP method/assumptions). If insufficient data, explain what's missing."}
        ],
        "step5":[
            {"key":"recognition", "type":"text", "question":"For each performance obligation, determine whether revenue is recognized over time or at a point in time, and specify the method of progress and key milestones with citations."}
        ]
    }

# ------------------------
# Writers: Excel + JSON
# ------------------------
import pandas as pd

def write_excel(out_path: str, outputs: StepOutputs):
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # Step 1
        s1 = []
        for k, f in outputs.step1.items():
            s1.append([k, f.answer, f.rationale, json.dumps(f.citations, ensure_ascii=False)])
        pd.DataFrame(s1, columns=["Key","Answer","Rationale","Citations"]).to_excel(writer, sheet_name="Step 1", index=False)

        # Step 2
        s2_rows = outputs.step2.get("rows", [])
        pd.DataFrame(s2_rows).to_excel(writer, sheet_name="Step 2", index=False)

        # Step 3
        pd.DataFrame([outputs.step3]).to_excel(writer, sheet_name="Step 3", index=False)

        # Step 4
        pd.DataFrame(outputs.step4.get("rows", [])).to_excel(writer, sheet_name="Step 4", index=False)

        # Step 5
        pd.DataFrame(outputs.step5.get("rows", [])).to_excel(writer, sheet_name="Step 5", index=False)

def write_json(out_path: str, outputs: StepOutputs):
    payload = {
        "step1": {k: {"answer": v.answer, "rationale": v.rationale, "citations": v.citations} for k, v in outputs.step1.items()},
        "step2": outputs.step2,
        "step3": outputs.step3,
        "step4": outputs.step4,
        "step5": outputs.step5
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

# ------------------------
# Orchestrators
# ------------------------
def run_ingest(args):
    client = get_client()
    vs_id = ensure_vector_store(client, args.contract_id)
    add_files_to_store(client, vs_id, args.files)
    print(f"[OK] Ingested {len(args.files)} file(s) into vector_store_id={vs_id} for contract_id={args.contract_id}")

def run_analyze(args):
    # Heuristics first (use local files if provided just to boost heuristics; RAG will read from vector store)
    # If user passes local_paths, we'll read them to build a text blob for heuristic pass.
    text_blob = ""
    for p in args.local_paths or []:
        text_blob += "\n\n" + extract_text_local(p)

    # Run heuristics
    step1_heur = analyze_step1_heur(text_blob)
    step2_heur = analyze_step2_heur(text_blob)
    step3_heur = analyze_step3_heur(text_blob)
    step4_heur = analyze_step4_heur(step2_heur, step3_heur)
    step5_heur = analyze_step5_heur(step2_heur, text_blob)

    outputs = StepOutputs(step1=step1_heur, step2=step2_heur, step3=step3_heur, step4=step4_heur, step5=step5_heur)

    # Only-fill-Unknowns via RAG
    client = get_client()
    vector_store_id = ensure_vector_store(client, args.contract_id)

    qmap = step_questions()

    # Step 1 detailed
    for q in qmap["step1"]:
        key = q["key"]
        if outputs.step1[key].answer == "Unknown":
            res = ask_rag(client, args.model, vector_store_id, q["question"], args.contract_id)
            # Normalize Y/N
            ans = res.get("answer","Unknown")
            if q["type"] == "yn":
                ansu = ans.strip().lower()
                if ansu.startswith("y"): ans = "Yes"
                elif ansu.startswith("n"): ans = "No"
                elif ansu.startswith("u"): ans = "Unknown"
            outputs.step1[key] = Finding(answer=ans, rationale=res.get("rationale",""), citations=res.get("citations", []))

    # Step 2..5: if heuristics empty/weak, ask RAG for a richer text answer.
    def enrich_text_step(step_key: str, target_container: Dict[str,Any], question_key: str):
        # Convert to a single question
        res = ask_rag(client, args.model, vector_store_id, qmap[step_key][0]["question"], args.contract_id)
        # We store the RAG answer as a note and leave the structured rows from heuristics as-is
        target_container["rag_note"] = {
            "answer": res.get("answer",""),
            "rationale": res.get("rationale",""),
            "citations": res.get("citations", [])
        }

    enrich_text_step("step2", outputs.step2, "promised_services")
    enrich_text_step("step3", outputs.step3, "transaction_price")
    enrich_text_step("step4", outputs.step4, "allocation")
    enrich_text_step("step5", outputs.step5, "recognition")

    # Write files
    write_excel(args.out_xlsx, outputs)
    write_json(args.out_json, outputs)

    print(f"[OK] Wrote:\n- Excel: {args.out_xlsx}\n- JSON:  {args.out_json}")

# ------------------------
# CLI
# ------------------------
def main():
    ap = argparse.ArgumentParser(description="ASC 606 Analyzer with OpenAI File Search (Vector Store)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_ingest = sub.add_parser("ingest", help="Create/find vector store for contract_id and upload files")
    ap_ingest.add_argument("--contract_id", required=True, help="ID to isolate this contract's vector store")
    ap_ingest.add_argument("--files", nargs="+", required=True, help="Contract files to upload (PDF/DOCX/TXT)")
    ap_ingest.set_defaults(func=run_ingest)

    ap_analyze = sub.add_parser("analyze", help="Run Step 1..5 analysis with heuristics + RAG fallback")
    ap_analyze.add_argument("--contract_id", required=True, help="Contract ID used during ingest")
    ap_analyze.add_argument("--out_xlsx", default="ASC606_Output.xlsx", help="Excel output path")
    ap_analyze.add_argument("--out_json", default="ASC606_Output.json", help="JSON output path")
    ap_analyze.add_argument("--model", default="gpt-4.1", help="OpenAI model for Responses API")
    ap_analyze.add_argument("--local_paths", nargs="*", help="Optional local file paths for heuristic pass (not required)")
    ap_analyze.set_defaults(func=run_analyze)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
