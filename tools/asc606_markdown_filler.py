#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASC 606 Contract Analyzer with Markdown Templates
------------------------------------------------
- Uses markdown templates (step1.md, step2.md, etc.) as direct prompts
- Progressive context building: each step includes previous step outputs
- Outputs: Filled markdown files for each step

Quick start
-----------
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...

# 1) Ingest a contract file (PDF/DOCX/TXT) into its own vector store
python asc606_markdown_filler.py ingest --contract_id C-001 --files "./contracts/ContractA.pdf"

# 2) Analyze it: fills all steps using markdown templates
python asc606_markdown_filler.py analyze --contract_id C-001 --output_dir "./output/C-001"

Notes
-----
- Each step uses the markdown template as a prompt
- Previous step outputs are included as context for subsequent steps
- Outputs are saved as filled markdown files
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
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
# Markdown template processing
# ------------------------
def load_markdown_template(step: str) -> str:
    """Load markdown template for a given step"""
    # Try multiple possible locations
    possible_paths = [
        f"questionset/{step}.md",
        f"../questionset/{step}.md",
        f"../../questionset/{step}.md"
    ]
    
    for template_path in possible_paths:
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
    
    raise FileNotFoundError(f"Template not found in any of: {possible_paths}")

def build_context_for_step(step: int, output_dir: str) -> str:
    """Build context by including previous step outputs"""
    context_parts = []
    
    for i in range(1, step):
        step_output_path = os.path.join(output_dir, f"step{i}_filled.md")
        if os.path.exists(step_output_path):
            with open(step_output_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:  # Only include non-empty results
                    context_parts.append(f"## Step {i} Results:\n{content}")
    
    return "\n\n".join(context_parts)

def ask_rag_with_template(client: "OpenAI", model: str, vector_store_id: str, 
                         template: str, context: str, contract_id: str) -> str:
    """
    Use the markdown template as a prompt and get filled response with proper formatting
    """
    # Build the full prompt
    if context:
        full_prompt = f"""Based on the attached contract files and the previous step results below, please fill out the following ASC 606 form:

{context}

---

{template}

Please replace all placeholders (marked with curly braces {{}}) with actual answers based on the contract documents. Provide specific evidence and citations where possible."""
    else:
        full_prompt = f"""Based on the attached contract files, please fill out the following ASC 606 form:

{template}

Please replace all placeholders (marked with curly braces {{}}) with actual answers based on the contract documents. Provide specific evidence and citations where possible."""

    system_msg = (
        "You are an ASC 606 accounting expert. Analyze the attached contract files and fill out the form completely. "
        "Replace all placeholders with specific answers based on the contract content. "
        "Always provide evidence and citations from the contract documents. "
        "Return the complete filled form in markdown format with proper formatting including: "
        "- Use **bold** for important terms and Yes/No answers "
        "- Use # for main headings, ## for subheadings "
        "- Use tables with proper markdown table syntax "
        "- Use bullet points and numbered lists where appropriate "
        "- Preserve all original markdown structure from the template"
    )

    # Use Responses API with file search (same as working implementation)
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": full_prompt}
        ],
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store_id]
        }],
        metadata={"contract_id": contract_id, "step": "markdown_fill"}
    )

    try:
        return resp.output_text.strip()
    except Exception:
        try:
            return resp.output[0].content[0].text.strip()
        except Exception:
            return "Error: Could not extract response content"

# ------------------------
# Orchestrators
# ------------------------
def run_ingest(args):
    client = get_client()
    vs_id = ensure_vector_store(client, args.contract_id)
    add_files_to_store(client, vs_id, args.files)
    print(f"[OK] Ingested {len(args.files)} file(s) into vector_store_id={vs_id} for contract_id={args.contract_id}")

def run_analyze(args):
    """Run analysis using markdown templates with progressive context"""
    client = get_client()
    vector_store_id = ensure_vector_store(client, args.contract_id)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Starting ASC 606 analysis for contract: {args.contract_id}")
    print(f"📁 Output directory: {output_dir}")
    print(f"🤖 Using model: {args.model}")
    
    # Process each step sequentially with progressive context
    for step_num in range(1, 6):
        step_name = f"step{step_num}"
        print(f"\n🔄 Processing {step_name.upper()}...")
        
        try:
            # Load template
            template = load_markdown_template(step_name)
            print(f"   📄 Loaded template: {len(template)} characters")
            
            # Build context from previous steps
            context = build_context_for_step(step_num, str(output_dir))
            if context:
                print(f"   📚 Context from previous steps: {len(context)} characters")
            else:
                print(f"   📚 No previous context (first step)")
            
            # Get filled response
            print(f"   🤖 Calling OpenAI API...")
            start_time = time.time()
            
            filled_content = ask_rag_with_template(
                client, args.model, vector_store_id, template, context, args.contract_id
            )
            
            elapsed = time.time() - start_time
            print(f"   ⏱️  API call completed in {elapsed:.2f} seconds")
            
            # Validate response
            if not filled_content or len(filled_content.strip()) < 100:
                print(f"   ⚠️  Warning: Response seems too short ({len(filled_content)} chars)")
            
            # Save filled content
            output_file = output_dir / f"{step_name}_filled.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(filled_content)
            
            print(f"   ✅ Saved {output_file} ({len(filled_content)} characters)")
            
        except Exception as e:
            print(f"   ❌ Error processing {step_name}: {str(e)}")
            # Create empty file to maintain sequence
            output_file = output_dir / f"{step_name}_filled.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# Error in {step_name}\n\nError: {str(e)}")
            continue
        
        # Add a small delay to avoid rate limiting
        time.sleep(2)
    
    print(f"\n🎉 Analysis complete! Output saved to: {output_dir}")
    print("\n📋 Generated files:")
    for step_num in range(1, 6):
        step_file = output_dir / f"step{step_num}_filled.md"
        if step_file.exists():
            size = step_file.stat().st_size
            print(f"  ✅ step{step_num}_filled.md ({size} bytes)")
        else:
            print(f"  ❌ step{step_num}_filled.md (missing)")

# ------------------------
# CLI
# ------------------------
def main():
    ap = argparse.ArgumentParser(description="ASC 606 Analyzer with Markdown Templates")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_ingest = sub.add_parser("ingest", help="Create/find vector store for contract_id and upload files")
    ap_ingest.add_argument("--contract_id", required=True, help="ID to isolate this contract's vector store")
    ap_ingest.add_argument("--files", nargs="+", required=True, help="Contract files to upload (PDF/DOCX/TXT)")
    ap_ingest.set_defaults(func=run_ingest)

    ap_analyze = sub.add_parser("analyze", help="Run Step 1..5 analysis using markdown templates")
    ap_analyze.add_argument("--contract_id", required=True, help="Contract ID used during ingest")
    ap_analyze.add_argument("--output_dir", default="./output", help="Directory to save filled markdown files")
    ap_analyze.add_argument("--model", default="gpt-5", help="OpenAI model for Responses API")
    ap_analyze.set_defaults(func=run_analyze)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
