import datetime
import json, re, math, os, sys, time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

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

# ---------- Utils: placeholders / normalization ----------

PLACEHOLDER_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")

def parse_placeholder_options(placeholder: str) -> Tuple[str, List[str]]:
    """
    Returns (kind, allowed_values). kind in {"choice","text"}
    Examples:
      "{{Yes/No/NA}}" -> ("choice", ["Yes","No","NA"])
      "{{text answer}}" -> ("text", [])
      "Yes/No/NA" -> ("choice", ["Yes","No","NA"])
    """
    # First try the {{...}} format
    m = PLACEHOLDER_RE.search(placeholder or "")
    if m:
        inner = m.group(1).strip()
        # Heuristic: if it contains "/", treat as enumerated options; else text
        if "/" in inner:
            vals = [v.strip() for v in inner.split("/")]
            return "choice", vals
        return "text", []
    
    # Handle simple format like "Yes/No/NA"
    if placeholder and "/" in placeholder:
        vals = [v.strip() for v in placeholder.split("/")]
        return "choice", vals
    
    return "text", []

def normalize_yes_no_na(x: str) -> str:
    t = (x or "").strip().lower()
    if t in {"y", "yes"}: return "Yes"
    if t in {"n", "no"}: return "No"
    if t in {"na", "n/a", "not applicable"}: return "NA"
    return x  # leave as-is if not recognized

def is_placeholder(value: str) -> bool:
    # Check for both {{...}} format and simple Yes/No/NA format
    if not value:
        return False
    value = value.strip()
    return (bool(PLACEHOLDER_RE.search(value)) or 
            value in ["Yes/No/NA", "Yes/No", "Yes/No/NA/Other"] or
            "/" in value and any(choice in value for choice in ["Yes", "No", "NA"]))

# ---------- Optional dependency & derivation support ----------

def safe_eval(expr: str, context: Dict[str, Any]) -> bool:
    """
    Tiny safe evaluator for visibility rules like: "S1.A.1 == 'Yes' and S1.A.2 == 'Yes'".
    Only allows names, strings, numbers, and operators: and/or/==/!=/in/not
    """
    allowed = {"and", "or", "not", "in", "True", "False", "None"}
    tokens = re.findall(r"[A-Za-z0-9_\.]+|==|!=|in|and|or|not|\(|\)|'[^']*'|\"[^\"]*\"", expr)
    # quick sanity check
    for t in tokens:
        if re.match(r"[A-Za-z_][A-Za-z0-9_\.]*", t):
            if t not in context and t not in allowed:
                # treat unknown names as empty string to avoid NameError
                context[t] = ""
    try:
        return bool(eval(expr, {"__builtins__": {}}, context))
    except Exception:
        return False

# ---------- Data structures ----------

@dataclass
class QA:
    qid: str
    question: str
    answer_template: str  # with {{ ... }}
    analysis_template: str  # with {{ ... }} or plain
    expected_answer: Optional[str] = None
    expected_analysis: Optional[str] = None
    visible_if: Optional[str] = None  # e.g., "S1.A.1 == 'Yes'"
    derive: Optional[str] = None      # small Python expression returning answer (string)
    # results
    actual_answer: Optional[str] = None
    actual_analysis: Optional[str] = None

@dataclass
class Context:
    # stores latest answers/analyses by qid
    answers: Dict[str, str] = field(default_factory=dict)
    analyses: Dict[str, str] = field(default_factory=dict)

    def to_brief_bullets(self, limit: int = 8) -> str:
        items = list(self.answers.items())[-limit:]
        lines = []
        for k, v in items:
            av = v
            an = self.analyses.get(k, "")
            # Truncate analysis to 80 chars to keep context manageable
            analysis_snippet = an[:80] + "..." if len(an) > 80 else an
            lines.append(f"- {k}: {av}" + (f" | {analysis_snippet}" if an else ""))
        return "\n".join(lines)

# ---------- LLM prompting ----------

def build_prompt(q: QA, ctx: Context) -> str:
    prior = ctx.to_brief_bullets()
    return f"""You are filling an ASC 606 form from contracts.

Earlier answers (for context):
{prior if prior else "- (none)"}

Question: {q.question}

Answer format: {q.answer_template}

Instructions:
- Follow the answer format exactly as specified above
- Use "Yes" if the evidence supports the statement or if it's reasonable to infer from the contract
- Use "No" if the evidence clearly contradicts the statement
- Use "NA" only if the question is completely irrelevant to this contract or no evidence exists at all
- For the "analysis" field: Quote the exact contract text that supports your answer. Look for specific clauses, terms, or provisions that directly relate to the question. If no relevant contract text exists, say "Not found in contract documents"
- Be more confident in your answers - if the contract contains relevant information, use "Yes" or "No" rather than defaulting to "NA"
- Focus on what the contract actually says, not on general business practices or company policies

Return strict JSON: {{"answer": "<value>", "analysis": "<evidence>"}} with no extra text.
"""

def call_llm(prompt: str) -> Dict[str, Any]:
    """
    Call OpenAI LLM to fill form questions using vector store. Must return {"answer": str, "analysis": str}
    """
    try:
        if not VECTOR_STORE_ID:
            print("❌ VECTOR_STORE_ID is missing in .env", file=sys.stderr)
            return {"answer": "NA", "analysis": "Vector store not configured"}
            
        print(f"   🔗 Using vector store: {VECTOR_STORE_ID}")
        print(f"   📝 Prompt length: {len(prompt)} characters")
        
        client = get_client()
        print(f"   🚀 Making API call to {MODEL}...")
        start_time = time.time()
        
        try:
            response = client.responses.create(
                model=MODEL,
                input=[
                    {
                        "role": "system",
                        "content": (
                            """You are a contract review assistant specializing in ASC 606. Use File Search over the provided 
                            vector store and answer ONLY from those documents. If evidence is insufficient, 
                            return 'No' and explain why. Return strict JSON: {"answer": "<value>", "analysis": "<evidence>"} 
                            with no extra text. The "analysis" must quote the exact supporting text (or say "Not found")."""
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=[{
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID]
                }],
                reasoning={"effort": "low"},
            )
            elapsed_time = time.time() - start_time
            print(f"   ✅ API call completed in {elapsed_time:.2f} seconds")
        except Exception as api_error:
            elapsed_time = time.time() - start_time
            print(f"   ❌ API call failed after {elapsed_time:.2f} seconds: {api_error}")
            raise api_error
        
        # Extract the response content
        content = response.output_text.strip()
        print(f"   📄 Full LLM response: {content}")
        
        # Try to parse as JSON
        try:
            result = json.loads(content)
            return {
                "answer": result.get("answer", "NA"),
                "analysis": result.get("analysis", "No analysis provided")
            }
        except json.JSONDecodeError:
            # If not JSON, try to extract answer and analysis from text
            lines = content.split('\n')
            answer = "NA"
            analysis = content
            
            for line in lines:
                if '"answer"' in line.lower() or 'answer:' in line.lower():
                    # Try to extract answer value
                    if ':' in line:
                        answer = line.split(':', 1)[1].strip().strip('"').strip("'")
                elif '"analysis"' in line.lower() or 'analysis:' in line.lower():
                    # Try to extract analysis value
                    if ':' in line:
                        analysis = line.split(':', 1)[1].strip().strip('"').strip("'")
            
            return {
                "answer": answer,
                "analysis": analysis
            }
            
    except Exception as e:
        print(f"❌ Error calling LLM: {e}", file=sys.stderr)
        return {"answer": "NA", "analysis": f"Error: {str(e)}"}

# ---------- Core runner ----------

def fill_form_step(step_json: Dict[str, Any], deps_map: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    deps_map (optional): {qid: {"visible_if": "...", "derive": "..."}} to keep dependencies
    separate from your base JSON.
    """
    ctx = Context()
    results: Dict[str, Dict[str, Any]] = {}

    # flatten questions in strict top-to-bottom order
    seq: List[QA] = []
    qcounter = 0

    def attach_meta(q: QA):
        if deps_map and q.qid in deps_map:
            q.visible_if = deps_map[q.qid].get("visible_if")
            q.derive = deps_map[q.qid].get("derive")

    def walk(node: Any, prefix: str = "S1", depth: int = 0):
        nonlocal qcounter
        if depth > 10:  # Prevent infinite recursion
            print(f"⚠️ Maximum recursion depth reached at {prefix}")
            return
            
        if isinstance(node, dict):
            # questions directly on node
            if "questions" in node and isinstance(node["questions"], list):
                print(f"   📋 Found {len(node['questions'])} questions in {prefix}")
                for item in node["questions"]:
                    qcounter += 1
                    qid = f"{prefix}.{qcounter}"
                    qa = QA(
                        qid=qid,
                        question=item.get("question","").strip(),
                        answer_template=str(item.get("answer","")).strip(),
                        analysis_template=str(item.get("analysis","")).strip(),
                        expected_answer=item.get("expected_answer"),
                        expected_analysis=item.get("expected_analysis"),
                    )
                    attach_meta(qa)
                    seq.append(qa)
            # nested sections
            for k in ["section", "sections", "step_section"]:
                if k in node and isinstance(node[k], list):
                    print(f"   📁 Found {len(node[k])} {k} sections in {prefix}")
                    for idx, sub in enumerate(node[k], start=1):
                        nxt_prefix = prefix  # keep same prefix so order rules the flow
                        walk(sub, nxt_prefix, depth + 1)
        elif isinstance(node, list):
            print(f"   📄 Processing list with {len(node)} items in {prefix}")
            for sub in node:
                walk(sub, prefix, depth + 1)

    # Prime the sequence
    walk(step_json, prefix="S1")

    # Main loop
    total_questions = len(seq)
    print(f"📊 Processing {total_questions} questions...")
    
    for i, q in enumerate(seq, 1):
        print(f"🔄 Processing question {i}/{total_questions}: {q.qid}")
        print(f"   Question: {q.question[:100]}{'...' if len(q.question) > 100 else ''}")
        
        # Visibility
        if q.visible_if:
            print(f"   🔍 Checking visibility rule: {q.visible_if}")
            if not safe_eval(q.visible_if, ctx.answers.copy()):
                print(f"   ⏭️ Skipping due to visibility rule")
                continue

        # Derivation rule
        if q.derive:
            print(f"   🧮 Applying derivation rule: {q.derive}")
            try:
                ans = str(eval(q.derive, {"__builtins__": {}}, {"ans": ctx.answers, "ana": ctx.analyses}))
                q.actual_answer = ans
                q.actual_analysis = "Derived by rule."
                ctx.answers[q.qid] = q.actual_answer
                ctx.analyses[q.qid] = q.actual_analysis
                results[q.qid] = {
                    "question": q.question,
                    "answer": q.actual_answer,
                    "analysis": q.actual_analysis,
                    "expected_answer": q.expected_answer,
                    "expected_analysis": q.expected_analysis
                }
                print(f"   ✅ Derived answer: {q.actual_answer}")
                continue
            except Exception as e:
                print(f"   ⚠️ Derivation failed: {e}, falling back to LLM")
                pass

        # Always use LLM for all questions - let LLM understand the template format
        print(f"   🤖 Calling LLM for question {q.qid}...")
        prompt = build_prompt(q, ctx)
        llm = call_llm(prompt)
        raw_answer = str(llm.get("answer","")).strip()
        analysis = str(llm.get("analysis","")).strip()
        print(f"   📤 LLM response: {raw_answer}")

        q.actual_answer = raw_answer
        q.actual_analysis = analysis

        # update state
        ctx.answers[q.qid] = q.actual_answer
        ctx.analyses[q.qid] = q.actual_analysis

        # persist
        results[q.qid] = {
            "question": q.question,
            "answer": q.actual_answer,
            "analysis": q.actual_analysis,
            "expected_answer": q.expected_answer,
            "expected_analysis": q.expected_analysis
        }
        
        print(f"   ✅ Completed question {q.qid}: {q.actual_answer}")
        print(f"   📈 Progress: {i}/{total_questions} ({i/total_questions*100:.1f}%)")
        print("-" * 60)

    return {
        "sequence": [r for _, r in results.items()],
        "answers_by_qid": {qid: r["answer"] for qid, r in results.items()},
        "analyses_by_qid": {qid: r["analysis"] for qid, r in results.items()},
    }

# ---------- JSON Output Generation ----------

def generate_filled_json(original_json: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a filled JSON with all placeholders replaced by LLM responses
    """
    # Debug: Check the structure of results
    print(f"🔍 Debug: Results structure - {type(results)}")
    print(f"🔍 Debug: Results keys - {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
    
    # Check if results has 'sequence' key
    if 'sequence' in results:
        print(f"🔍 Debug: Found 'sequence' with {len(results['sequence'])} items")
        for i, item in enumerate(results['sequence'][:2]):  # Show first 2
            print(f"  Item {i}: {list(item.keys()) if isinstance(item, dict) else type(item)}")
    
    # Create a mapping from question text to filled values
    question_to_result = {}
    
    # Try different ways to access the results
    if 'sequence' in results:
        for item in results['sequence']:
            if isinstance(item, dict) and "question" in item and "answer" in item:
                question_to_result[item["question"]] = {
                    "answer": item["answer"],
                    "analysis": item.get("analysis", "")
                }
    
    print(f"🔍 Debug: Found {len(question_to_result)} questions with results")
    for q, r in list(question_to_result.items())[:3]:  # Show first 3
        print(f"  - '{q[:50]}...' -> '{r['answer']}'")
    
    def fill_placeholders_recursive(node: Any) -> Any:
        if isinstance(node, dict):
            filled_node = {}
            for key, value in node.items():
                if key == "answer" and isinstance(value, str):
                    # Check if this is a placeholder that should be replaced
                    if "{{" in value or value in ["Yes/No/NA", "Yes/No", "text answer", "any remarks", "Evidences that supports answer"]:
                        # Find matching question and replace
                        question_text = node.get("question", "")
                        if question_text in question_to_result:
                            print(f"🔄 Replacing '{value}' with '{question_to_result[question_text]['answer']}' for question: {question_text[:50]}...")
                            filled_node[key] = question_to_result[question_text]["answer"]
                        else:
                            print(f"⚠️ No match found for question: {question_text[:50]}...")
                            filled_node[key] = value  # Keep original if no match
                    else:
                        filled_node[key] = value
                elif key == "analysis" and isinstance(value, str):
                    # Check if this is a placeholder that should be replaced
                    if "{{" in value or value in ["Evidences that supports answer"]:
                        # Find matching question and replace
                        question_text = node.get("question", "")
                        if question_text in question_to_result:
                            filled_node[key] = question_to_result[question_text]["analysis"]
                        else:
                            filled_node[key] = value  # Keep original if no match
                    else:
                        filled_node[key] = value
                else:
                    filled_node[key] = fill_placeholders_recursive(value)
            return filled_node
        elif isinstance(node, list):
            return [fill_placeholders_recursive(item) for item in node]
        else:
            return node
    
    return fill_placeholders_recursive(original_json)

# ---------- Metrics: expected vs actual ----------

def compare_expected_vs_actual(results: Dict[str, Any]) -> Dict[str, Any]:
    seq = results["sequence"]
    total = 0
    correct = 0
    rows = []
    for r in seq:
        exp = (r.get("expected_answer") or "").strip()
        act = (r.get("answer") or "").strip()
        if exp:
            total += 1
            ok = (exp == act)
            if ok: correct += 1
            rows.append({"question": r["question"], "expected": exp, "actual": act, "match": ok})
    acc = (correct / total) if total else None
    return {"accuracy": acc, "detail": rows}


# ---------- Main function ----------

def main():
    """Main function to run the form filling process"""
    # Load step1.json
    # step1_json_path = "../questionset/variant2/step1.json"
    filename = "step2.json"
    step1_json_path = "../questionset/variant2/" + filename
    
    try:
        with open(step1_json_path, 'r', encoding='utf-8') as f:
            step_1_json = json.load(f)
        print(f"✅ Loaded step1.json from {step1_json_path}")
    except FileNotFoundError:
        print(f"❌ File not found: {step1_json_path}")
        print("Please ensure the file exists in the correct path.")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Set deps_map to None as requested
    deps_map = None
    
    print("🚀 Starting form filling process...")
    print("=" * 60)
    
    try:
        # Run the form filling process
        step_result = fill_form_step(step_1_json, deps_map)
        
        # Generate filled JSON
        print("\n📄 Generating filled JSON...")
        print(f"🔍 Results available: {len(step_result.get('sequence', []))} questions processed")
        filled_json = generate_filled_json(step_1_json, step_result)
        
        # Save filled JSON to file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{filename}_filled_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(filled_json, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved filled JSON to {output_file}")
        
        # Show a sample of what was filled
        print("\n🔍 Sample of filled results:")
        for i, result in enumerate(step_result.get('sequence', [])[:3]):
            print(f"  {i+1}. {result.get('question', '')[:50]}... -> {result.get('answer', '')}")
        
        # Compare expected vs actual results
        report = compare_expected_vs_actual(step_result)
        
        # Print results
        print(f"\n📊 Accuracy: {report['accuracy']}")
        print("=" * 60)
        print("Detailed Results:")
        print("=" * 60)
        
        for row in report["detail"]:
            match_status = "✅" if row["match"] else "❌"
            print(f"{match_status} {row['expected']} -> {row['actual']} | {row['question']}")
        
        print("=" * 60)
        print(f"Total questions: {len(report['detail'])}")
        print(f"Correct answers: {sum(1 for row in report['detail'] if row['match'])}")
        print(f"Accuracy: {report['accuracy']:.2%}" if report['accuracy'] is not None else "No expected answers to compare")
        
    except Exception as e:
        print(f"❌ Error during form filling: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
