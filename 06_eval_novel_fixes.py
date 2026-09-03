# 06_eval_novel_fixes.py — RQ3: Novel Fix Quality Scoring vs Expert Panel (unified)
#   python3 06_eval_novel_fixes.py --model qwen|deepseek
#
# Scores the PAPER'S 35 novel-source commits (novel_fixes.jsonl) on
# generalizability/sustainability/effectiveness, compared to expert mean 3.80.

import os, sys, json, time, requests, hashlib
from collections import defaultdict
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc
from tqdm import tqdm

args = mc.get_args("RQ3 — novel fix quality scoring vs expert panel (N=35)")
M    = mc.MODELS[args.model]
P    = mc.paths(M["suffix"])
IN   = os.path.join(cfg.DATA_DIR, "novel_fixes.jsonl")   # the paper's 35, not the per-model pool
OUT  = P["novel_eval"]

def _norm_tag(t):
    """novel_fixes.jsonl stores lowercase 'tag' (e.g. 'reentrancy'); normalise to DASP name."""
    t = (t or "").strip().lower()
    for k, v in {
        "reentrancy":"Reentrancy","access":"Access Control","arithmetic":"Arithmetic",
        "unchecked":"Unchecked Return Values","denial":"Denial of Service","dos":"Denial of Service",
        "randomness":"Bad Randomness","front":"Front Running","time":"Time Manipulation",
        "short":"Short Address",
    }.items():
        if k in t: return v
    return "Unknown"

def _stable_id(r):
    """novel_fixes.jsonl has no usable hash; key resume on content of before+after.
    Prefer a previously-stamped _eval_id so output records match input records."""
    if r.get("_eval_id"): return r["_eval_id"]
    h = r.get("hash")
    if h: return h
    blob = ((r.get("before") or "") + (r.get("after") or ""))[:500]
    return hashlib.md5(blob.encode("utf-8", "ignore")).hexdigest()

EVAL_PROMPT = """You are an expert smart contract security reviewer.

A developer fixed a smart contract vulnerability. Below is the vulnerability
category and the actual code change (before/after). A written description may
NOT be provided — in that case, INFER the fixing strategy directly from the
code diff. This fix is not documented in any academic paper.

Rate the FIXING STRATEGY on 3 dimensions (1 = very low, 5 = very high):
  Generalizability:         How applicable is this approach to similar contracts?
  Long-term Sustainability: Will this fix remain effective as code evolves?
  Effectiveness:            How well does this approach resolve the vulnerability?

Vulnerability category: {category}
Commit message: {message}
{code_section}

IMPORTANT: Judge the fixing strategy that the code implements. Infer it from the
diff if no prose description is given. Do NOT lower scores merely because a
written description is absent — a missing description is not a flaw in the fix.
Use your security expertise; always produce a score.

Respond ONLY with valid JSON:
{{
  "generalizability":         <integer 1-5>,
  "long_term_sustainability": <integer 1-5>,
  "effectiveness":            <integer 1-5>,
  "avg_expert_score":         <mean of 3 scores rounded to 2 decimals>,
  "reasoning":                "<one sentence>"
}}"""

def get_category(r):
    # novel_fixes.jsonl uses lowercase 'tag'; normalise it, else fall back to other fields.
    cat = (r.get("paper_category") or r.get("llm_category")
           or r.get("llm_category_deepseek") or r.get("dasp_category"))
    if cat:
        return cat
    if r.get("tag"):
        return _norm_tag(r.get("tag"))
    return "Unknown"

import difflib

def get_code(r):
    """Return full before/after (no premature truncation)."""
    before = (r.get("pre_fix") or r.get("before") or "")
    after  = (r.get("post_fix") or r.get("after") or "")
    return before, after

def make_diff(before, after, ctx=3, max_chars=2500):
    """Unified diff of before->after: strips the shared file header, shows only
    changed lines with a little context. This is what the model should judge —
    the actual change — not two near-identical full files."""
    if not before and not after:
        return ""
    diff = difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile="before", tofile="after", lineterm="", n=ctx,
    )
    body = "\n".join(list(diff)[2:])  # drop the ---/+++ header lines
    if not body.strip():
        # identical (or whitespace-only) — fall back to showing the after code
        body = after[:max_chars]
    return body[:max_chars]

def code_section(before, after):
    d = make_diff(before, after)
    if d:
        return ("Code change (unified diff; lines starting with '-' were removed, "
                "'+' were added):\n" + d)
    return "(no code change available)"

def call_llm(prompt):
    try:
        r = requests.post(cfg.OLLAMA_URL, json={
            "model":   M["ollama"],
            "prompt":  prompt,
            "stream":  False,
            "options": {**cfg.OLLAMA_OPTIONS, "temperature": 0.1, "num_predict": 512, **M.get("opts", {})},
        }, timeout=M["timeout"])
        return mc.extract_json(r.json().get("response", ""))
    except requests.exceptions.Timeout:
        return {"_error": "TIMEOUT"}
    except Exception as ex:
        return {"_error": str(ex)}

def main():
    if not os.path.exists(IN):
        sys.exit(f"ERROR: {IN} not found. It is produced by 02_load_dataset.py "
                 f"(the paper's 35 novel-source commits).")
    if args.fresh and os.path.exists(OUT):
        os.remove(OUT); print(f"Fresh run — deleted {OUT}")

    fixes = mc.load_jsonl(IN)
    if args.sample:
        fixes = fixes[:args.sample]
    # resume keyed on a stable content id, since novel_fixes.jsonl has no hash
    done_ids = {_stable_id(r) for r in mc.load_jsonl(OUT)}
    to_do = [r for r in fixes if _stable_id(r) not in done_ids]
    print(f"Model: {M['ollama']} | RQ3 set (paper's 35): {len(fixes)} | "
          f"done {len(done_ids)} | remaining {len(to_do)}")

    scored, no_code_count = [], 0
    cat_scores = defaultdict(list)
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    with open(OUT, "a", buffering=1) as f:
        for fix in tqdm(to_do, desc=f"RQ3 [{M['suffix']}]"):
            fix["_eval_id"] = _stable_id(fix)   # stamp so resume + dedup work
            cat = get_category(fix)
            before, after = get_code(fix)
            if not before and not after:
                no_code_count += 1
            ev = call_llm(EVAL_PROMPT.format(
                category=cat, message=(fix.get("message") or "(not available)")[:200],
                code_section=code_section(before, after)))
            if ev.get("_error"):
                ev = {"generalizability":0,"long_term_sustainability":0,"effectiveness":0,
                      "avg_expert_score":0,"reasoning":f"Error: {ev['_error']}"}
            else:
                g = ev.get("generalizability",0); s = ev.get("long_term_sustainability",0)
                e = ev.get("effectiveness",0)
                if all(isinstance(x,(int,float)) and 1<=x<=5 for x in (g,s,e)):
                    avg = round((g+s+e)/3, 2)
                    ev["avg_expert_score"] = avg
                    scored.append(avg); cat_scores[cat].append(avg)
                else:
                    ev = {"generalizability":0,"long_term_sustainability":0,"effectiveness":0,
                          "avg_expert_score":0,"reasoning":"Model returned invalid scores."}
            fix["llm_evaluation"] = ev
            f.write(json.dumps(fix) + "\n")
            time.sleep(0.05)

    llm_avg = sum(scored)/len(scored) if scored else 0
    print(f"\n{'='*55}\nRQ3 — {M['ollama']}  (paper's 35 novel-source commits)\n{'='*55}")
    print(f"Set size: {len(fixes)} | scored: {len(scored)} | no-code: {no_code_count} | "
          f"failed: {len(to_do)-len(scored)-no_code_count}")
    print(f"LLM avg: {llm_avg:.2f}  (paper {cfg.PAPER_NOVEL_AVG:.2f}, gap {llm_avg-cfg.PAPER_NOVEL_AVG:+.2f})")
    print(f"\n{'Category':<28}{'n':>4}{'mu':>8}")
    print("-"*42)
    for cat in cfg.DASP_CATEGORIES[:-1]:
        sc = cat_scores.get(cat, [])
        if sc:
            print(f"  {cat:<26}{len(sc):>4}{sum(sc)/len(sc):>8.2f}  (paper {cfg.PAPER_NOVEL_BY_CAT.get(cat,'-')})")
    print(f"\nSaved {OUT}")

if __name__ == "__main__":
    main()