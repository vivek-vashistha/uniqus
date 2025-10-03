import os
import sys
from io import BytesIO
from datetime import datetime
from typing import Iterable, List, Optional

import requests
from dotenv import load_dotenv
from openai import OpenAI

# =========================
# Configuration
# =========================
LOG_FILE = "upload_log.txt"
# Limit to these file types (set to None to allow all)
ALLOWED_EXTS = {".pdf", ".txt", ".md", ".docx", ".csv", ".pptx"}

# =========================
# Env + Client
# =========================
load_dotenv()

api_key = os.getenv("DIRECT_OPENAI_API_KEY")
if not api_key:
    print("❌ DIRECT_OPENAI_API_KEY is missing in .env", file=sys.stderr)
    sys.exit(1)

client = OpenAI(api_key=api_key)

# Optional: if you want to ADD to an existing vector store, set this in .env
# VECTOR_STORE_ID=vs_abc123
EXISTING_VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")


# =========================
# Helpers
# =========================
def log_upload(filename: str, vector_store_id: str):
    """Append upload info to a log file with timestamp."""
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(
            f"{datetime.now().isoformat()} | File: {filename} | VectorStoreID: {vector_store_id}\n"
        )


def is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def create_file(client: OpenAI, file_path: str) -> tuple[str, str]:
    """
    Upload a single file (local path or URL) to OpenAI Files.
    Returns (file_id, file_name).
    """
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
    """
    Walks a folder and returns list of file paths that match allowed extensions.
    If allowed_exts is None, returns all files.
    """
    files = []
    for root, _, filenames in os.walk(folder_path):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if (allowed_exts is None) or (ext in allowed_exts):
                files.append(os.path.join(root, fname))
    return files


def ensure_vector_store(client: OpenAI, existing_id: Optional[str], name: str = "knowledge_base"):
    """
    If existing_id provided, reuse that vector store. Otherwise, create a new one.
    Returns an object with .id
    """
    if existing_id:
        class _VS:  # tiny wrapper to look like the API object
            def __init__(self, _id): self.id = _id
        print(f"ℹ️ Reusing existing vector store: {existing_id}")
        return _VS(existing_id)
    vs = client.vector_stores.create(name=name)
    print(f"🆕 Created vector store → id: {vs.id} | name: {name}")
    return vs


def add_file_to_vector_store(client: OpenAI, vector_store_id: str, file_id: str):
    added = client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )
    return added


# =========================
# Main
# =========================
def upload_folder_as_knowledge_base(folder_path: str, vector_store_name: str = "knowledge_base"):
    if not os.path.isdir(folder_path):
        print(f"❌ Folder not found: {folder_path}", file=sys.stderr)
        sys.exit(1)

    # 1) Create or reuse a vector store
    vector_store = ensure_vector_store(client, EXISTING_VECTOR_STORE_ID, vector_store_name)

    # 2) Gather files
    paths = iter_local_files(folder_path, ALLOWED_EXTS)
    if not paths:
        print(f"⚠️ No files found in '{folder_path}' with extensions {ALLOWED_EXTS}")
        return

    print(f"📦 Found {len(paths)} file(s) to upload in '{folder_path}'")

    # 3) Upload each file and attach to the vector store
    successes, failures = 0, 0
    for path in paths:
        try:
            file_id, file_name = create_file(client, path)
            add_file_to_vector_store(client, vector_store.id, file_id)
            log_upload(file_name, vector_store.id)
            print(f"🔗 Attached to vector store {vector_store.id} and logged.")
            successes += 1
        except Exception as e:
            print(f"❌ Failed for {path}: {e}", file=sys.stderr)
            failures += 1

    # 4) Summary + list
    print(f"\n✅ Done. Success: {successes} | Failed: {failures}")
    listing = client.vector_stores.files.list(vector_store_id=vector_store.id)
    print("📚 Files currently in vector store:", listing)

    print(f"📝 Log file: {LOG_FILE}")
    print(f"💡 Vector Store ID: {vector_store.id} (save this and put it in .env as VECTOR_STORE_ID to reuse)")


if __name__ == "__main__":
    # Example: change this to your folder (use r"..." on Windows to avoid backslash escapes)
    FOLDER_PATH = r"Contract 1"
    upload_folder_as_knowledge_base(FOLDER_PATH, vector_store_name="knowledge_base")
