
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASC 606 Contract Analyzer with OpenAI Responses API + Vector Store (File Search)
-------------------------------------------------------------------------------
- Isolation: One vector store per contract_id (prevents cross-contract mixing)
- Analyze: Reads step markdown prompts and overwrites each with LLM answers
- No Excel/JSON writers; ingest flow unchanged

Quick start
-----------
pip install -r requirements.txt

# 1) Ingest a contract file (PDF/DOCX/TXT) into its own vector store
python asc606_rag_filler.py ingest --contract_id C-001 --files "./contracts/ContractA.pdf"

# 2) Analyze prompts in questionset and write answers back to the same files
python asc606_rag_filler.py analyze --contract_id C-001

Optional:
- Add more files to the same contract_id with another `ingest` call.
- Point `--model` to your preferred OpenAI model (e.g., gpt-4.1, o3-mini, gpt-4o-mini).
- Provide custom prompt files via --step_files path\\to\\step1.md path\\to\\step2.md ...

Notes
-----
- The script uses OpenAI's Responses API with the File Search tool. The vector store is attached per request to
  guarantee isolation. See inline comments where the vector_store_id is passed.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path


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
def ask_rag_markdown(client: "OpenAI", model: str, vector_store_id: str, prompt_text: str, contract_id: str) -> str:
    """
    Call Responses API with File Search restricted to vector_store_id, using the provided
    markdown prompt, and return the model's markdown text directly.
    """
    system_msg = (
        "You are an ASC 606 accounting assistant. Use ONLY retrieved file-search results when citing. "
        "Respond in Markdown suitable to overwrite the user's prompt file, replacing placeholders with final answers. "
        "If evidence is insufficient, clearly mark unknowns and explain what's missing. Include brief citations."
    )

    resp = client.responses.create(
        model=model,
        input=[
            {"role":"system","content":system_msg},
            {"role":"user","content":prompt_text}
        ],
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store_id]
        }],
        metadata={"contract_id": contract_id}
    )

    try:
        return resp.output_text.strip()
    except Exception:
        try:
            return (resp.output[0].content[0].text or "").strip()
        except Exception:
            return ""

 

# ------------------------
# Orchestrators
# ------------------------
def run_ingest(args):
    client = get_client()
    vs_id = ensure_vector_store(client, args.contract_id)
    add_files_to_store(client, vs_id, args.files)
    print(f"[OK] Ingested {len(args.files)} file(s) into vector_store_id={vs_id} for contract_id={args.contract_id}")

def run_analyze(args):
    client = get_client()
    vector_store_id = ensure_vector_store(client, args.contract_id)

    # Resolve repo root (this file is in tools/ → parent is repo root)
    root_dir = Path(__file__).resolve().parent.parent

    # Determine step files
    if getattr(args, "step_files", None):
        step_paths = [Path(p) for p in args.step_files]
    else:
        qdir = root_dir / "questionset"
        step_paths = [qdir / f"step{i}.md" for i in range(1, 6)]

    output_dir = root_dir / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    updated = 0
    date_str = datetime.now().strftime("%Y%m%d")
    for p in step_paths:
        if not p.exists():
            print(f"[WARN] Skipping missing file: {p}")
            continue
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            prompt_text = f.read()

        answer_md = ask_rag_markdown(client, args.model, vector_store_id, prompt_text, args.contract_id)

        stem = p.stem
        suffix = p.suffix or ".md"
        out_path = output_dir / f"{stem}_{args.contract_id}_{date_str}_llm_result{suffix}"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(answer_md)
        print(f"[OK] Wrote response to {out_path}")
        updated += 1

    print(f"[OK] Analysis complete for contract_id={args.contract_id}; wrote {updated} file(s) to {output_dir}")

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

    ap_analyze = sub.add_parser("analyze", help="Read step markdowns, call LLM with vector store, write outputs into data/output with _output suffix")
    ap_analyze.add_argument("--contract_id", required=True, help="Contract ID used during ingest")
    ap_analyze.add_argument("--model", default="gpt-4.1", help="OpenAI model for Responses API")
    ap_analyze.add_argument("--step_files", nargs="*", help="Optional list of markdown prompt files to process in order")
    ap_analyze.set_defaults(func=run_analyze)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
