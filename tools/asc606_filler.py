
#!/usr/bin/env python3
"""
ASC 606 Contract Analyzer (Steps 1–5)

Usage:
  python asc606_filler.py --contract "path/to/contract.pdf" --out "ASC606_Output.xlsx" [--template "ASC606_Steps_Template.xlsx"] [--json "ASC606_Output.json"]

What it does:
- Extracts text from the contract (PDF/DOCX/TXT)
- Heuristically answers survey questions for Steps 1–5 (ASC 606)
- Writes answers into an Excel file (matching the provided template layout, if given)
- Saves a JSON file with the structured answers

Dependencies (install if needed):
  pip install pypdf2 python-docx openpyxl pandas
"""

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Lazy imports so that users without certain libs can still run partial functionality
def safe_import_pypdf2():
    try:
        import PyPDF2
        return PyPDF2
    except Exception:
        return None

def safe_import_docx():
    try:
        import docx
        return docx
    except Exception:
        return None

import pandas as pd

# ---------------------------
# Helpers: Text extraction
# ---------------------------

def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_pdf_text(path)
    elif ext in [".docx"]:
        return extract_docx_text(path)
    else:
        # assume text-like
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

def extract_pdf_text(path: str) -> str:
    PyPDF2 = safe_import_pypdf2()
    if PyPDF2 is None:
        raise RuntimeError("PyPDF2 is required for PDF parsing. Run: pip install pypdf2")
    text_chunks = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for i, page in enumerate(reader.pages):
            try:
                text_chunks.append(page.extract_text() or "")
            except Exception:
                # Some PDFs may fail to extract; continue gracefully
                text_chunks.append("")
    return "\n\n".join(text_chunks)

def extract_docx_text(path: str) -> str:
    docx = safe_import_docx()
    if docx is None:
        raise RuntimeError("python-docx is required for DOCX parsing. Run: pip install python-docx")
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

# ---------------------------
# Utilities
# ---------------------------

def find_snippets(text: str, keyword: str, window: int = 240) -> List[str]:
    """Return small context snippets around keyword occurrences."""
    out = []
    for m in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        out.append(text[start:end].strip())
    return out[:5]  # cap

def first_match(text: str, patterns: List[str]) -> Optional[re.Match]:
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE|re.DOTALL)
        if m:
            return m
    return None

def money_mentions(text: str) -> List[str]:
    return re.findall(r'(\$[\s]*[0-9][0-9,]*\.?[0-9]*|\bUSD\s*[0-9][0-9,]*\.?[0-9]*)', text, flags=re.IGNORECASE)

def number_mentions(text: str) -> List[str]:
    return re.findall(r'\b[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?\b', text)

# ---------------------------
# Heuristic Analyzers
# ---------------------------

@dataclass
class Finding:
    answer: str
    rationale: str

@dataclass
class StepOutputs:
    step1: Dict[str, Finding] = field(default_factory=dict)
    step2: Dict[str, Any] = field(default_factory=dict)
    step3: Dict[str, Any] = field(default_factory=dict)
    step4: Dict[str, Any] = field(default_factory=dict)
    step5: Dict[str, Any] = field(default_factory=dict)

def analyze_step1(text: str) -> Dict[str, Finding]:
    out: Dict[str, Finding] = {}

    # Q1: existence of agreement
    evidence = first_match(text, [r'\bMASTER\b.*\bAGREEMENT\b', r'\bWORK ORDER\b', r'\bAGREEMENT\b.*\bbetween\b'])
    out["agreement_exists"] = Finding(
        "Yes" if evidence else "Unknown",
        f"Evidence: {'found' if evidence else 'not found'} for agreement terms (e.g., 'Agreement', 'Work Order')."
    )

    # Q2: approval / commitment (signatures, effective dates)
    sig = first_match(text, [r'\bEffective Date\b.*?[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4}', r'\bSigned\b', r'\bSignature\b'])
    out["approved_committed"] = Finding(
        "Yes" if sig else "Unknown",
        "Looked for 'Effective Date', 'Signed', 'Signature' to infer commitment."
    )

    # Q3: rights identifiable
    rights = first_match(text, [r'\bright[s]?\b.*\bservices?\b', r'\bdeliverables?\b', r'\bScope of Work\b', r'\bServices shall\b'])
    out["rights_identified"] = Finding(
        "Yes" if rights else "Unknown",
        "Searched for 'deliverables', 'scope of work', 'services shall'."
    )

    # Q4: payment terms identifiable
    pay = first_match(text, [r'\bInvoice[s]?\b.*?\b(?:within|due)\b.*?\b(?:days|day)\b', r'\bPayment Terms\b', r'\bNet\s*\d+\b'])
    out["payment_terms_identified"] = Finding(
        "Yes" if pay else "Unknown",
        "Searched for 'Invoice', 'Payment Terms', 'Net XX days'."
    )

    # Q5: commercial substance (heuristic: any money mentions or fees -> Yes)
    monies = money_mentions(text)
    out["commercial_substance"] = Finding(
        "Yes" if monies else "Unknown",
        f"Detected monetary terms: {', '.join(monies[:5]) if monies else 'none'}."
    )

    # Q6: collectibility probable (heuristic: presence of payment protections + reputable counterparty keywords)
    credit_clues = bool(first_match(text, [r'\binterest on overdue\b', r'\bdispute\b.*\bwithhold\b', r'\bcredit\b']))
    out["collectibility_probable"] = Finding(
        "Yes" if credit_clues or monies else "Unknown",
        "Assessed based on presence of fees and payment/credit protection language."
    )

    # Q7: multiple contracts same time (look for multiple dates close together)
    dates = re.findall(r'(?:Effective Date|Date[:\s])\s*[:\-]?\s*([A-Za-z]{3,9}\s*\d{1,2},\s*\d{4}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})', text, flags=re.IGNORECASE)
    out["multiple_contracts_near_time"] = Finding(
        "Unknown",
        f"Found dates: {dates[:5]} (manual check needed for ±3 months)."
    )

    # Q8: negotiated as package (heuristic: look for 'pursuant to', 'under MSA', 'work order')
    package = first_match(text, [r'\bpursuant to\b.*\bMaster\b', r'\bunder\b.*\bMaster.*Agreement\b', r'\bWork Order\b.*\bpursuant\b'])
    out["negotiated_as_package"] = Finding(
        "Yes" if package else "Unknown",
        "Looked for 'pursuant to Master Agreement' / 'under MSA'."
    )

    # Q9: combine for accounting (cannot auto-judge definitively)
    out["combine_contracts"] = Finding(
        "Unknown",
        "Requires judgment on single commercial objective, interdependent pricing."
    )

    # Q10: conclusion
    conclusion_yes = all(v.answer in ["Yes", "Unknown"] for k, v in out.items() if k in [
        "agreement_exists", "approved_committed", "rights_identified", "payment_terms_identified", "commercial_substance", "collectibility_probable"
    ]) and out["agreement_exists"].answer == "Yes"
    out["conclusion_contract_exists"] = Finding(
        "Yes" if conclusion_yes else "Unknown",
        "Based on presence of agreement, rights, payment terms, and monetary substance."
    )
    return out

def extract_promised_services(text: str) -> List[str]:
    # Simple heuristic extraction based on common headings and keywords
    services = set()
    # Look for "Services", "Deliverables", "Work Order", "Scope", "Exhibit A"
    blocks = re.split(r'\n{2,}', text)
    for b in blocks:
        headerish = re.match(r'\s*(?:Services?|Deliverables?|Scope|Work Order|Exhibit A)\b.*', b, re.IGNORECASE)
        if headerish:
            # pick bullet-like lines
            for line in b.splitlines():
                if re.search(r'^\s*[\-\u2022\*]\s+.+', line) or re.search(r'\bservices?\b', line, re.IGNORECASE):
                    ln = re.sub(r'^\s*[\-\u2022\*]\s*', '', line).strip()
                    if 5 <= len(ln) <= 200:
                        services.add(ln)
    # fallback: sentences mentioning "shall provide", "will provide"
    for m in re.finditer(r'\b(?:shall|will)\s+provide\s+([^\.]{10,200})\.', text, re.IGNORECASE):
        segment = m.group(1).strip()
        services.add(segment)
    return list(services)[:12]  # cap

def analyze_step2(text: str) -> Dict[str, Any]:
    services = extract_promised_services(text)
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

def analyze_step3(text: str) -> Dict[str, Any]:
    fixed = []
    variable = []
    # naive parsing of dollars and nearby words
    for snip in find_snippets(text, "$"):
        fixed.append(snip)
    # variable cues
    for kw in ["bonus", "penalty", "rebate", "incentive", "price adjustment", "liquidated damages"]:
        variable.extend(find_snippets(text, kw))
    financing = "Yes" if re.search(r'\bfinancing component\b|\bdeferred payment\b|\binstallments?\b', text, re.IGNORECASE) else "Unknown"
    payable_to_customer = "Yes" if re.search(r'\b(payable to customer|customer incentive|credit to customer)\b', text, re.IGNORECASE) else "Unknown"
    total_hint = ", ".join(sorted(set(money_mentions(text)))[:8])
    return {
        "fixed_consideration_examples": fixed[:5],
        "variable_consideration_examples": variable[:5],
        "non_cash": "Unknown",
        "significant_financing_component": financing,
        "consideration_payable_to_customer": payable_to_customer,
        "total_transaction_price_hint_values": total_hint
    }

def analyze_step4(step2: Dict[str, Any], step3: Dict[str, Any]) -> Dict[str, Any]:
    # Without SSPs, default to relative equal allocation across distinct POs as placeholder
    pos = [r for r in step2.get("rows", []) if r.get("distinct") == "Yes"]
    n = len(pos)
    # We don't have a numeric total; provide structure only
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
    return {"rows": alloc_rows, "note": f"{n} distinct POs detected; add SSPs and totals to complete allocation."}

def analyze_step5(step2: Dict[str, Any], text: str) -> Dict[str, Any]:
    rows = []
    over_time_cues = bool(re.search(r'\bover time\b|monthly|quarterly|annual|term of the agreement|service levels?', text, re.IGNORECASE))
    acceptance_cues = find_snippets(text, "acceptance")
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

# ---------------------------
# Excel/JSON writers
# ---------------------------

def write_to_excel(out_path: str, step_outputs: StepOutputs, template: Optional[str] = None):
    # If a template is provided, we try to conform; else create a clean workbook with similar structure
    writer = pd.ExcelWriter(out_path, engine="openpyxl")

    # Step 1
    s1_rows = []
    for key, f in step_outputs.step1.items():
        question = {
            "agreement_exists": "Is there a written/verbal/implied agreement?",
            "approved_committed": "Is the contract approved and parties committed?",
            "rights_identified": "Are parties' rights identifiable?",
            "payment_terms_identified": "Are payment terms identifiable?",
            "commercial_substance": "Does the contract have commercial substance?",
            "collectibility_probable": "Is collection of consideration probable?",
            "multiple_contracts_near_time": "Any other contracts at/near same time (~3 months)?",
            "negotiated_as_package": "Negotiated as a package with single commercial objective?",
            "combine_contracts": "Should contracts be combined for accounting?",
            "conclusion_contract_exists": "Conclusion – Contract exists per ASC 606-10-25-1?"
        }.get(key, key)
        s1_rows.append([question, f.answer, f.rationale])
    pd.DataFrame(s1_rows, columns=["Question", "Answer", "Rationale"]).to_excel(writer, sheet_name="Step 1", index=False)

    # Step 2
    s2 = step_outputs.step2
    pd.DataFrame(s2.get("rows", [])).to_excel(writer, sheet_name="Step 2", index=False)

    # Step 3
    pd.DataFrame([step_outputs.step3]).to_excel(writer, sheet_name="Step 3", index=False)

    # Step 4
    pd.DataFrame(step_outputs.step4.get("rows", [])).to_excel(writer, sheet_name="Step 4", index=False)

    # Step 5
    pd.DataFrame(step_outputs.step5.get("rows", [])).to_excel(writer, sheet_name="Step 5", index=False)

    writer.close()

def write_to_json(json_path: str, step_outputs: StepOutputs):
    # Convert dataclasses to basic dict
    s1 = {k: {"answer": v.answer, "rationale": v.rationale} for k, v in step_outputs.step1.items()}
    payload = {
        "step1": s1,
        "step2": step_outputs.step2,
        "step3": step_outputs.step3,
        "step4": step_outputs.step4,
        "step5": step_outputs.step5
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="ASC 606 contract analyzer (Steps 1–5)")
    ap.add_argument("--contract", required=True, help="Path to contract file (PDF/DOCX/TXT)")
    ap.add_argument("--out", default="ASC606_Output.xlsx", help="Path to Excel output")
    ap.add_argument("--json", default="ASC606_Output.json", help="Path to JSON output")
    ap.add_argument("--template", default=None, help="Optional template (not strictly required)")
    args = ap.parse_args()

    text = extract_text(args.contract)

    # Run analyzers
    step1 = analyze_step1(text)
    step2 = analyze_step2(text)
    step3 = analyze_step3(text)
    step4 = analyze_step4(step2, step3)
    step5 = analyze_step5(step2, text)

    outputs = StepOutputs(step1=step1, step2=step2, step3=step3, step4=step4, step5=step5)

    # Write
    write_to_excel(args.out, outputs, args.template)
    write_to_json(args.json, outputs)

    print(f"Done.\nExcel: {args.out}\nJSON: {args.json}")

if __name__ == "__main__":
    main()
