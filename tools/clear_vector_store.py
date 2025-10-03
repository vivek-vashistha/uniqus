import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# Load environment variables
load_dotenv()

# Read API key
api_key = os.getenv("DIRECT_OPENAI_API_KEY")

# Initialize client
client = OpenAI(api_key=api_key)

# Replace with your vector store ID
VECTOR_STORE_ID = "vs_68df8395caf88191ba7edc132f2e9867"

# Log file path (same as upload script)
LOG_FILE = "upload_log.txt"

def log_action(action: str, vector_store_id: str):
    """Append actions (create/delete) to the same log file."""
    with open(LOG_FILE, "a") as log:
        log.write(f"{datetime.now().isoformat()} | Action: {action} | VectorStoreID: {vector_store_id}\n")

# Delete the vector store
delete_result = client.vector_stores.delete(
    vector_store_id=VECTOR_STORE_ID
)

print("🗑️ Delete result:", delete_result)

# Log deletion
log_action("DELETE", VECTOR_STORE_ID)
print(f"✅ Logged deletion of vector store {VECTOR_STORE_ID} in {LOG_FILE}")
