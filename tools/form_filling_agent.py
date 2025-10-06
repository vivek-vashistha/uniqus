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
    """
    m = PLACEHOLDER_RE.search(placeholder or "")
    if not m:
        return "text", []
    inner = m.group(1).strip()
    # Heuristic: if it contains "/", treat as enumerated options; else text
    if "/" in inner:
        vals = [v.strip() for v in inner.split("/")]
        return "choice", vals
    return "text", []

def normalize_yes_no_na(x: str) -> str:
    t = (x or "").strip().lower()
    if t in {"y", "yes"}: return "Yes"
    if t in {"n", "no"}: return "No"
    if t in {"na", "n/a", "not applicable"}: return "NA"
    return x  # leave as-is if not recognized

def is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.search(value or ""))

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

    def to_brief_bullets(self, limit: int = 12) -> str:
        items = list(self.answers.items())[-limit:]
        lines = []
        for k, v in items:
            av = v
            an = self.analyses.get(k, "")
            lines.append(f"- {k}: {av}" + (f" | evidence: {an[:240]}" if an else ""))
        return "\n".join(lines)

# ---------- LLM prompting ----------

def build_prompt(q: QA, ctx: Context) -> str:
    kind, choices = parse_placeholder_options(q.answer_template)
    allowed = ""
    format_req = (
        'Return strict JSON: {"answer": "<value>", "analysis": "<evidence>"} '
        'with no extra text.'
    )
    if kind == "choice" and choices:
        allowed = f"Choose one of: {', '.join(choices)}"
    else:
        allowed = "Free-text answer is allowed."
    prior = ctx.to_brief_bullets()
    return f"""You are filling an ASC 606 form from contracts.

Earlier answers (for context):
{prior if prior else "- (none)"}

Question: {q.question}

Constraints:
- {allowed}
- If not determinable from the provided evidence, use "NA".
- The "analysis" must quote the exact supporting text (or say "Not found").

{format_req}
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

        # If not a placeholder, just copy through
        if not is_placeholder(q.answer_template):
            print(f"   📝 Using template answer: {q.answer_template}")
            q.actual_answer = str(q.answer_template)
            q.actual_analysis = str(q.analysis_template or "")
            ctx.answers[q.qid] = q.actual_answer
            ctx.analyses[q.qid] = q.actual_analysis
            results[q.qid] = {
                "question": q.question,
                "answer": q.actual_answer,
                "analysis": q.actual_analysis,
                "expected_answer": q.expected_answer,
                "expected_analysis": q.expected_analysis
            }
            print(f"   ✅ Template answer: {q.actual_answer}")
            continue

        # LLM fill
        print(f"   🤖 Calling LLM for question {q.qid}...")
        prompt = build_prompt(q, ctx)
        llm = call_llm(prompt)
        raw_answer = str(llm.get("answer","")).strip()
        analysis = str(llm.get("analysis","")).strip()
        print(f"   📤 LLM response: {raw_answer}")

        kind, choices = parse_placeholder_options(q.answer_template)
        if kind == "choice" and choices:
            print(f"   🎯 Normalizing choice from {raw_answer} to one of {choices}")
            # normalize the categorical value
            if set(map(str.lower, choices)) == {"yes","no","na"}:
                raw_answer = normalize_yes_no_na(raw_answer)
            # force into allowed set
            if raw_answer not in choices:
                # best-effort snap
                lowered = [c.lower() for c in choices]
                try:
                    idx = lowered.index(raw_answer.lower())
                    raw_answer = choices[idx]
                except ValueError:
                    raw_answer = "NA" if "NA" in choices else choices[0]
            print(f"   ✅ Normalized to: {raw_answer}")

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
    step1_json_path = "../questionset/variant2/step1.json"
    
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
        
        # Compare expected vs actual results
        report = compare_expected_vs_actual(step_result)
        
        # Print results
        print(f"Accuracy: {report['accuracy']}")
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
