#!/usr/bin/env python3
"""
OpenAI Vector Store CLI Tool
A command-line interface for managing OpenAI vector stores and performing QnA operations.
"""

import os
import sys
import json
import argparse
from io import BytesIO
from datetime import datetime
from typing import Iterable, List, Optional, Literal
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configuration
LOG_FILE = "upload_log.txt"
ALLOWED_EXTS = {".pdf", ".txt", ".md", ".docx", ".csv", ".pptx"}

# Environment variables
API_KEY = os.getenv("DIRECT_OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")

# Initialize client only when needed
def get_client():
    if not API_KEY:
        print("❌ DIRECT_OPENAI_API_KEY is missing in .env", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=API_KEY)


class ChecklistRow(BaseModel):
    """Schema for checklist responses"""
    description: str
    yes_no: Literal["Yes", "No", "N/A"]
    analysis: str


def log_action(action: str, vector_store_id: str, filename: str = None):
    """Log actions to the log file"""
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        timestamp = datetime.now().isoformat()
        if filename:
            log.write(f"{timestamp} | Action: {action} | File: {filename} | VectorStoreID: {vector_store_id}\n")
        else:
            log.write(f"{timestamp} | Action: {action} | VectorStoreID: {vector_store_id}\n")


def is_url(path: str) -> bool:
    """Check if path is a URL"""
    return path.startswith("http://") or path.startswith("https://")


def create_file(file_path: str) -> tuple[str, str]:
    """Upload a single file (local path or URL) to OpenAI Files"""
    client = get_client()
    if is_url(file_path):
        resp = requests.get(file_path)
        resp.raise_for_status()
        file_content = BytesIO(resp.content)
        file_name = file_path.split("/")[-1] or "downloaded_file"
        file_tuple = (file_name, file_content)
        created = client.files.create(file=file_tuple, purpose="assistants")
    else:
        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as fh:
            created = client.files.create(file=fh, purpose="assistants")
    print(f"✅ Uploaded file → id: {created.id} | name: {file_name}")
    return created.id, file_name


def iter_local_files(folder_path: str, allowed_exts: Optional[Iterable[str]]) -> List[str]:
    """Walk a folder and return list of file paths that match allowed extensions"""
    files = []
    for root, _, filenames in os.walk(folder_path):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if (allowed_exts is None) or (ext in allowed_exts):
                files.append(os.path.join(root, fname))
    return files


def ensure_vector_store(existing_id: Optional[str], name: str = "knowledge_base"):
    """Create or reuse a vector store"""
    client = get_client()
    if existing_id:
        class _VS:
            def __init__(self, _id): 
                self.id = _id
        print(f"ℹ️ Reusing existing vector store: {existing_id}")
        return _VS(existing_id)
    
    vs = client.vector_stores.create(name=name)
    print(f"🆕 Created vector store → id: {vs.id} | name: {name}")
    return vs


def add_file_to_vector_store(vector_store_id: str, file_id: str):
    """Add a file to the vector store"""
    client = get_client()
    added = client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )
    return added


def upload_command(args):
    """Handle upload command"""
    folder_path = args.folder
    vector_store_name = args.name or "knowledge_base"
    use_existing = args.use_existing
    
    if not os.path.isdir(folder_path):
        print(f"❌ Folder not found: {folder_path}", file=sys.stderr)
        sys.exit(1)

    # Create or reuse vector store
    existing_id = VECTOR_STORE_ID if use_existing else None
    vector_store = ensure_vector_store(existing_id, vector_store_name)

    # Gather files
    paths = iter_local_files(folder_path, ALLOWED_EXTS)
    if not paths:
        print(f"⚠️ No files found in '{folder_path}' with extensions {ALLOWED_EXTS}")
        return

    print(f"📦 Found {len(paths)} file(s) to upload in '{folder_path}'")

    # Upload each file and attach to vector store
    successes, failures = 0, 0
    for path in paths:
        try:
            file_id, file_name = create_file(path)
            add_file_to_vector_store(vector_store.id, file_id)
            log_action("UPLOAD", vector_store.id, file_name)
            print(f"🔗 Attached to vector store {vector_store.id} and logged.")
            successes += 1
        except Exception as e:
            print(f"❌ Failed for {path}: {e}", file=sys.stderr)
            failures += 1

    # Summary
    print(f"\n✅ Done. Success: {successes} | Failed: {failures}")
    client = get_client()
    listing = client.vector_stores.files.list(vector_store_id=vector_store.id)
    print("📚 Files currently in vector store:", listing)

    print(f"📝 Log file: {LOG_FILE}")
    print(f"💡 Vector Store ID: {vector_store.id} (save this and put it in .env as VECTOR_STORE_ID to reuse)")


def qna_command(args):
    """Handle QnA command"""
    if not VECTOR_STORE_ID:
        print("❌ VECTOR_STORE_ID missing in .env", file=sys.stderr)
        sys.exit(1)

    question = args.question
    if not question:
        print("❌ Question is required", file=sys.stderr)
        sys.exit(1)

    schema = ChecklistRow.model_json_schema()

    try:
        client = get_client()
        resp = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        """You are a contract review assistant specializing in ASC 606. Use File Search over the provided 
                        vector store and answer ONLY from those documents. If evidence is insufficient, 
                        return 'No' and explain why. Output must match the JSON schema.
                        JSON schema:
                        {
                            "description": "The description of the checklist row",
                            "yes_no": "Yes, No or N/A",
                            "analysis": "The analysis of the checklist row"
                        }
                        Example:
                        {
                            "description": "Is the contract approved and are the parties committed to their obligations (ASC 606-10-25-1(a))?",
                            "yes_no": "Yes",
                            "analysis": "The contract is approved and the parties are committed to their obligations (ASC 606-10-25-1(a))"
                        }
                        """
                    ),
                },
                {"role": "user", "content": question},
            ],
            tools=[{
                "type": "file_search",
                "vector_store_ids": [VECTOR_STORE_ID]
            }],
            reasoning={"effort": "low"},
        )
        
        print("=" * 60)
        print(f"Question: {question}")
        print("=" * 60)
        print("Response:")
        print(resp.output_text)
        print("=" * 60)
            
    except Exception as e:
        print(f"❌ Error during QnA: {e}", file=sys.stderr)
        sys.exit(1)


def clear_command(args):
    """Handle clear command"""
    vector_store_id = args.vector_store_id or VECTOR_STORE_ID
    
    if not vector_store_id:
        print("❌ Vector store ID is required. Use --vector-store-id or set VECTOR_STORE_ID in .env", file=sys.stderr)
        sys.exit(1)

    try:
        client = get_client()
        delete_result = client.vector_stores.delete(
            vector_store_id=vector_store_id
        )
        print("🗑️ Delete result:", delete_result)
        log_action("DELETE", vector_store_id)
        print(f"✅ Logged deletion of vector store {vector_store_id} in {LOG_FILE}")
    except Exception as e:
        print(f"❌ Error deleting vector store: {e}", file=sys.stderr)
        sys.exit(1)


def list_command(args):
    """Handle list command"""
    vector_store_id = args.vector_store_id or VECTOR_STORE_ID
    
    if not vector_store_id:
        print("❌ Vector store ID is required. Use --vector-store-id or set VECTOR_STORE_ID in .env", file=sys.stderr)
        sys.exit(1)

    try:
        client = get_client()
        listing = client.vector_stores.files.list(vector_store_id=vector_store_id)
        print(f"📚 Files in vector store {vector_store_id}:")
        for file in listing.data:
            print(f"  - {file.id}: {file.filename}")
    except Exception as e:
        print(f"❌ Error listing files: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="OpenAI Vector Store CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s upload ./data --name "my_knowledge_base"
  %(prog)s qna "Is the contract approved?"
  %(prog)s clear --vector-store-id vs_abc123
  %(prog)s list
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload documents to vector store')
    upload_parser.add_argument('folder', help='Folder path containing documents to upload')
    upload_parser.add_argument('--name', help='Name for the vector store (default: knowledge_base)')
    upload_parser.add_argument('--use-existing', action='store_true', 
                             help='Use existing vector store from VECTOR_STORE_ID env var')

    # QnA command
    qna_parser = subparsers.add_parser('qna', help='Ask questions based on vector store content')
    qna_parser.add_argument('question', help='Question to ask about the documents')

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear/delete a vector store')
    clear_parser.add_argument('--vector-store-id', help='Vector store ID to delete (uses VECTOR_STORE_ID env var if not provided)')

    # List command
    list_parser = subparsers.add_parser('list', help='List files in vector store')
    list_parser.add_argument('--vector-store-id', help='Vector store ID to list (uses VECTOR_STORE_ID env var if not provided)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate command handler
    if args.command == 'upload':
        upload_command(args)
    elif args.command == 'qna':
        qna_command(args)
    elif args.command == 'clear':
        clear_command(args)
    elif args.command == 'list':
        list_command(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
