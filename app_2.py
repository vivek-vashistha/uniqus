import os, json
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI

# --- env
load_dotenv()
API_KEY = os.getenv("DIRECT_OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5")  # use your exact GPT-5 variant
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")
if not API_KEY: raise RuntimeError("DIRECT_OPENAI_API_KEY missing in .env")
if not VECTOR_STORE_ID: raise RuntimeError("VECTOR_STORE_ID missing in .env")

client = OpenAI(api_key=API_KEY)

# --- target schema
class ChecklistRow(BaseModel):
    description: str
    yes_no: Literal["Yes", "No"]
    analysis: str

def answer_with_file_search(question: str) -> ChecklistRow:
    schema = ChecklistRow.model_json_schema()

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
        reasoning={ "effort": "low" },
    )
    return resp


if __name__ == "__main__":
    # q = "Is the contract approved and are the parties committed to their obligations (ASC 606-10-25-1(a))?"
    # q = "Can the payment terms for the goods and services be identified (ASC 606-10-25-1(c)) ?"
    # q = "Are there any contracts entered into at or near the same time (rebuttable presumption 3 months) with the same customer or related parties of the customer?"


    q = "Contracts were negotiated as a package with a single commercial objective (e.g. contract would be loss-making without taking into account the consideration received under another contract)?"
    # q = "Consideration in one contract depends on price or performance of the other contract (e.g. failure to perform under one contract affect the amount paid under another contract)?"
    # q = "Goods or services promised in the contracts (or some goods or services promised in each contract) are a single performance obligation in accordance with paragraphs 606-10-25-14 through 25-22 ?"

    # q = "Has the contract commercial substance (ASC 606-10-25-1(d)) ?"
    row = answer_with_file_search(q)
    # print(row)
    # print("----------------------------------------------------------")
    print("----------------------------------------------------------")
    print(row.output_text)
    # print_row(row)
