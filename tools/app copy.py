import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from pprint import pprint

# Load environment variables from .env
load_dotenv()

# Read values
api_key = os.getenv("DIRECT_OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL")

# Initialize client
client = OpenAI(api_key=api_key)

# client = OpenAI()

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]
    model: str
    price: float

response = client.responses.parse(
    # model="gpt-4o-2024-08-06",
    model=model_name,
    input=[
        {"role": "system", "content": "Extract the event information."},
        {
            "role": "user",
            "content": "Alice and Bob are going to a science fair on Friday.",
        },
    ],
    text_format=CalendarEvent,
    reasoning={ "effort": "low" },
    # text={ "verbosity": "low" },
    tools=[{
        "type": "file_search",
        "vector_store_ids": ["<vector_store_id>"]
    }]
)

event = response.output_parsed
pprint(event)
print("----------------------------------------------------------")
pprint(response)