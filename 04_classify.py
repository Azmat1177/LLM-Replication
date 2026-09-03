# 04_classify.py — RQ1: Vulnerability Classification (unified)
#   python3 04_classify.py --model 7b|14b|deepseek
import os, sys, json, time, requests
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc
from tqdm import tqdm

args  = mc.get_args("RQ1 — vulnerability classification")
M     = mc.MODELS[args.model]
P     = mc.paths(M["suffix"])
OUT   = P["classified"]

PROMPT = """You are a smart contract security expert.

Classify this Solidity vulnerability fix using EXACTLY ONE category from the DASP TOP 10:
- Reentrancy
- Access Control
- Arithmetic
- Unchecked Return Values
- Denial of Service
- Bad Randomness
- Front Running
- Time Manipulation
- Short Address
- Unknown

Commit message: {message}

Code diff / fix:
{diff}

Respond ONLY with valid JSON, no other text:
{{
  "category":   "<one category from the list above>",
  "swc_id":     "<SWC ID e.g. SWC-107, or null>",
  "confidence": "<high|medium|low>",
  "reasoning":  "<one sentence explaining your choice>"
}}"""

def normalise(raw):
    raw = (raw or "").strip().lower()
    for k, v in {
        "reentrancy":"Reentrancy", "access":"Access Control",
        "arithmetic":"Arithmetic", "unchecked":"Unchecked Return Values",
        "denial":"Denial of Service", "dos":"Denial of Service",
        "randomness":"Bad Randomness", "front":"Front Running",
        "time":"Time Manipulation", "short":"Short Address",
    }.items():
        if k in raw:
            return v
    return "Unknown"

def call_llm(prompt):
    try:
        r = requests.post(cfg.OLLAMA_URL, json={
            "model":   M["ollama"],
            "prompt":  prompt,
            "stream":  False,
            "options": {**cfg.OLLAMA_OPTIONS, "temperature": 0.0, **M.get("opts", {})},
        }, timeout=M["timeout"])
        text = r.json().get("response", "")
    except requests.exceptions.Timeout:
        return {"category": "Unknown", "swc_id": None,
                "confidence": "low", "reasoning": "TIMEOUT"}
    except Exception as ex:
        return {"category": "Unknown", "swc_id": None,
                "confidence": "low", "reasoning": str(ex)}
    parsed = mc.extract_json(text)
    if not parsed:
        return {"category": "Unknown", "swc_id": None,
                "confidence": "low", "reasoning": mc.strip_think(text)[:100]}
    return parsed

def main():
    if args.fresh and os.path.exists(OUT):
        os.remove(OUT); print(f"Fresh run — deleted {OUT}")

    commits = mc.load_jsonl(mc.RAW_COMMITS)
    if args.sample:
        commits = commits[:args.sample]

    done  = mc.load_done(OUT)
    to_do = [c for c in commits if c.get("hash", "") not in done]
    print(f"Model: {M['ollama']}  | total {len(commits)} | done {len(done)} | remaining {len(to_do)}")

    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    with open(OUT, "a", buffering=1) as f:
        for commit in tqdm(to_do, desc=f"RQ1 [{M['suffix']}]"):
            prompt = PROMPT.format(
                message=(commit.get("message") or "")[:300],
                diff=(commit.get("diff") or commit.get("pre_fix") or "")[:1500],
            )
            out = call_llm(prompt)
            commit["llm_classification"] = out
            commit["llm_category"]   = normalise(out.get("category", ""))
            commit["paper_category"] = normalise(commit.get("dasp_category", ""))
            commit["categories_match"] = (
                commit["llm_category"].lower() == commit["paper_category"].lower()
            )
            f.write(json.dumps(commit) + "\n")
            time.sleep(0.05)

    results = mc.load_jsonl(OUT)
    labeled = [r for r in results if r.get("paper_category", "Unknown") != "Unknown"]
    matches = sum(1 for r in labeled if r.get("categories_match"))
    acc = matches / len(labeled) * 100 if labeled else 0
    print(f"\n{'='*55}\nTASK A — {M['ollama']}\n{'='*55}")
    print(f"Records: {len(results)} | valid labels: {len(labeled)} | matches: {matches} ({acc:.1f}%)")
    print(f"Paper labeling kappa: {cfg.PAPER_RESULTS['cohens_kappa_labeling']}  "
          f"[confirmed 0.72 in paper Sec 5.3 — note: accuracy != kappa, not directly comparable]")

    cat_n, cat_m = defaultdict(int), defaultdict(int)
    for r in labeled:
        p = r["paper_category"]; cat_n[p] += 1
        if r.get("categories_match"): cat_m[p] += 1
    print(f"\n{'Category':<26} {'N':>5} {'Match%':>8}")
    print("-"*42)
    for cat in cfg.DASP_CATEGORIES[:-1]:
        if cat_n.get(cat):
            print(f"{cat:<26} {cat_n[cat]:>5} {cat_m[cat]/cat_n[cat]*100:>7.0f}%")
    print(f"\nSaved {OUT}\nNext: 05_compare_fixes.py --model {args.model}")

if __name__ == "__main__":
    main()