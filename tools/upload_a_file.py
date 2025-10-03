import requests
from io import BytesIO
import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from pprint import pprint
from datetime import datetime

# Load environment variables from .env
load_dotenv()

# Read values
api_key = os.getenv("DIRECT_OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL")

# Initialize client
client = OpenAI(api_key=api_key)

LOG_FILE = "upload_log.txt"

def log_upload(filename: str, vector_store_id: str):
    """Append upload info to a log file with timestamp."""
    with open(LOG_FILE, "a") as log:
        log.write(f"{datetime.now().isoformat()} | File: {filename} | VectorStoreID: {vector_store_id}\n")

def create_file(client, file_path):
    if file_path.startswith("http://") or file_path.startswith("https://"):
        # Download the file content from the URL
        response = requests.get(file_path)
        file_content = BytesIO(response.content)
        file_name = file_path.split("/")[-1]
        file_tuple = (file_name, file_content)
        result = client.files.create(
            file=file_tuple,
            purpose="assistants"
        )
    else:
        # Handle local file path
        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as file_content:
            result = client.files.create(
                file=file_content,
                purpose="assistants"
            )
    print("file.id ---------   ", result.id)
    return result.id, file_name

# Replace with your own file path or URL
file_id, file_name = create_file(client, "https://cdn.openai.com/API/docs/deep_research_blog.pdf")
# file_id, file_name = create_file(client, "Contract 1\Contract 1 file 2 2.pdf")
# file_id, file_name = create_file(client, "Contract 1\Contract 1 file 3 2.pdf")

# Create a vector store
vector_store = client.vector_stores.create(
    name="knowledge_base"
)
print("vector_store.id ---------   ", vector_store.id)

# Add the file to the vector store
result = client.vector_stores.files.create(
    vector_store_id=vector_store.id,
    file_id=file_id
)
print("result ---------   ", result)

# List files in the vector store
result = client.vector_stores.files.list(
    vector_store_id=vector_store.id
)
print("result ----2-----   ", result)

# Log the upload
log_upload(file_name, vector_store.id)
print(f"✅ Logged upload: {file_name} → {vector_store.id} (see {LOG_FILE})")
