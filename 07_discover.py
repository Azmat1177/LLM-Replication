# 07_discover.py — RQ4: Novel Strategy Discovery (unified)
#   python3 07_discover.py --model 7b|14b|deepseek [--retry-errors]
import os, sys, json, time, requests, argparse
from collections import defaultdict
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc
from tqdm import tqdm

# extend the shared parser with --retry-errors
def get_args():
    p = argparse.ArgumentParser(description="RQ4 — novel strategy discovery")
    p.add_argument("--model", required=True, choices=list(mc.MODELS.keys()))
    p.add_argument("--fresh",  action="store_true")
    p.add_argument("--sample", type=int, default=None)
    p.add_argument("--retry-errors", action="store_true",
                   help="Re-process commits that previously errored/timed out")
    return p.parse_args()

args = get_args()
M    = mc.MODELS[args.model]
P    = mc.paths(M["suffix"])
IN   = P["novel"]
OUT  = P["discovered"]
REPORT = os.path.join(cfg.RESULTS_DIR, f"extension_report_{M['suffix']}.txt")
INPUT_KNOWN   = os.path.join(cfg.REPO_PATH, "new_fixes.json")
ZERO_LIT_CATS = {"bad randomness", "time manipulation", "short address"}
MAX_RETRIES   = 3

def load_known():
    by_cat = defaultdict(list)
    for cat, fixes in cfg.LITERATURE_GUIDELINES.items():
        for t in fixes:
            if t: by_cat[cat.lower().strip()].append(t)
    if not os.path.exists(INPUT_KNOWN):
        print(f"WARNING: {INPUT_KNOWN} not found — literature guidelines only.")
        return dict(by_cat)
    with open(INPUT_KNOWN) as f:
        data = json.load(f)
    for fix in data:
        tag  = (fix.get("tag") or "Unknown").lower().strip()
        desc = fix.get("description") or ""
        if not desc:
            after  = (fix.get("after") or "").strip()[:300]
            before = (fix.get("before") or "").strip()[:150]
            desc = (f"Post-fix pattern: {after}" if after
                    else f"Pre-fix pattern (replaced): {before}" if before else "")
        if desc: by_cat[tag].append(desc)
    print(f"Known strategies: {sum(len(v) for v in by_cat.values())} across {len(by_cat)} cats")
    return dict(by_cat)

COMPARISON_PROMPT = """You are a smart contract security research assistant.

The following are ALL known novel fixing strategies for "{category}"
vulnerabilities that human experts have already documented:

KNOWN STRATEGIES:
{known_strategies}

Now examine this developer commit that was NOT found in academic literature:

Category:       {category}
Commit message: {message}
Pre-fix code:
{before}
Post-fix code:
{after}

1. Does this commit implement the same SECURITY PRINCIPLE as any known
   strategy above? (semantic match, not literal code) If yes, state which.
2. If not, describe the NEW fixing approach in one reusable sentence.

Respond ONLY with valid JSON:
{{
  "matches_known_strategy":   true or false,
  "matched_strategy":         "<name or null>",
  "is_genuinely_new":         true or false,
  "new_strategy_description": "<reusable description or null>",
  "confidence":               "<high|medium|low>",
  "reasoning":                "<one sentence>"
}}"""

PROPOSE_ZERO_LIT_PROMPT = """You are a smart contract security expert and researcher.

The vulnerability category "{category}" currently has NO documented
practical fixing strategies in any academic paper.

Examine this real developer fix:
Commit message: {message}
Pre-fix code:
{before}
Post-fix code:
{after}

Describe the general strategy, why it works, and when to apply it.

Respond ONLY with valid JSON:
{{
  "strategy_name":        "<short name>",
  "strategy_description": "<reusable description>",
  "security_rationale":   "<why it fixes the vuln>",
  "applicability":        "<when to use>",
  "limitations":          "<when NOT to use>",
  "fills_gap":            "No prior strategy documented for this category",
  "confidence":           "<high|medium|low>"
}}"""

PROPOSE_NEW_GENERAL_PROMPT = """You are a smart contract security expert and researcher.

The category "{category}" has documented strategies, but this commit uses
a DIFFERENT approach.

Known strategies for "{category}":
{known_strategies}

Examine this fix:
Commit message: {message}
Pre-fix code:
{before}
Post-fix code:
{after}

Describe the new strategy, why it works, when to use it, and what gap it fills.

Respond ONLY with valid JSON:
{{
  "strategy_name":        "<short name>",
  "strategy_description": "<reusable description>",
  "security_rationale":   "<why it fixes the vuln>",
  "applicability":        "<when to use>",
  "limitations":          "<when NOT to use>",
  "fills_gap":            "<what known strategies miss>",
  "confidence":           "<high|medium|low>"
}}"""

def call_llm(prompt, max_tokens=512, retries=MAX_RETRIES):
    last = "unknown"
    for attempt in range(1, retries+1):
        try:
            r = requests.post(cfg.OLLAMA_URL, json={
                "model": M["ollama"], "prompt": prompt, "stream": False,
                "options": {**cfg.OLLAMA_OPTIONS, "temperature": 0.1, "num_predict": max_tokens, **M.get("opts", {})},
            }, timeout=M["timeout"])
            parsed = mc.extract_json(r.json().get("response", ""))
            if parsed:
                return parsed
            last = f"NO_JSON (attempt {attempt})"
            time.sleep(2**attempt); continue
        except requests.exceptions.Timeout:
            last = f"TIMEOUT (attempt {attempt})"
            if attempt < retries: time.sleep(2**attempt)
            continue
        except Exception as ex:
            return {"_error": f"ERROR: {ex}"}
    return {"_error": f"PERMANENT_FAIL: {last}"}

def load_done(path, include_errors):
    done = set()
    for rec in mc.load_jsonl(path):
        h = rec.get("hash", "")
        if not h: continue
        is_err = (rec.get("discovery_type") == "error"
                  or rec.get("extension_analysis", {}).get("_error"))
        if include_errors or not is_err:
            done.add(h)
    return done

def discover():
    if not os.path.exists(IN):
        sys.exit(f"ERROR: {IN} not found. Run 05_compare_fixes.py --model {args.model} first.")
    if args.fresh and os.path.exists(OUT):
        os.remove(OUT); print(f"Fresh run — deleted {OUT}")

    novel = mc.load_jsonl(IN)
    if args.sample:
        novel = novel[:args.sample]
    known_by_cat = load_known()

    if args.retry_errors and os.path.exists(OUT):
        keep = [r for r in mc.load_jsonl(OUT)
                if not (r.get("discovery_type")=="error"
                        or r.get("extension_analysis",{}).get("_error"))]
        with open(OUT, "w") as f:
            for r in keep: f.write(json.dumps(r)+"\n")
        print(f"--retry-errors: kept {len(keep)} good records, errors will be retried")
        done = mc.load_done(OUT)
    else:
        done = load_done(OUT, include_errors=True)

    to_do = [c for c in novel if c.get("hash","") not in done]
    print(f"Model: {M['ollama']} | novel {len(novel)} | done {len(done)} | remaining {len(to_do)}")

    genuinely_new, matches_known, proposed_new, errors = [], [], [], []
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    with open(OUT, "a", buffering=1) as f:
        for commit in tqdm(to_do, desc=f"RQ4 [{M['suffix']}]"):
            cat = (commit.get("paper_category") or commit.get("llm_category")
                   or commit.get("llm_category_deepseek") or "Unknown").lower().strip()
            message = (commit.get("message") or "")[:200]
            before  = (commit.get("pre_fix") or commit.get("before") or commit.get("diff") or "")[:500]
            after   = (commit.get("post_fix") or commit.get("after") or "")[:500]
            known   = known_by_cat.get(cat, [])
            known_text = "\n".join(f"  - {s[:200]}" for s in known) if known else "  None documented yet."

            q1 = call_llm(COMPARISON_PROMPT.format(category=cat, known_strategies=known_text,
                                                   message=message, before=before, after=after))
            commit["extension_analysis"] = q1
            if q1.get("_error"):
                commit["discovery_type"] = "error"; errors.append(commit)
                f.write(json.dumps(commit)+"\n"); time.sleep(0.05); continue
            if q1.get("is_genuinely_new"):
                commit["discovery_type"] = "new_strategy"; genuinely_new.append(commit)
                tmpl = PROPOSE_ZERO_LIT_PROMPT if cat in ZERO_LIT_CATS else PROPOSE_NEW_GENERAL_PROMPT
                proposal = call_llm(tmpl.format(category=cat, known_strategies=known_text,
                                                message=message, before=before, after=after),
                                    max_tokens=768)
                commit["proposed_new_strategy"] = proposal
                if proposal and not proposal.get("_error"):
                    proposed_new.append(commit)
            else:
                commit["discovery_type"] = "matches_known"; matches_known.append(commit)
                commit["proposed_new_strategy"] = None
            f.write(json.dumps(commit)+"\n"); time.sleep(0.05)

    # dedup near-identical strategy descriptions (first 60 chars, case-insensitive)
    seen, dedup, by_cat_dedup = set(), 0, defaultdict(int)
    for c in genuinely_new:
        key = (c.get("extension_analysis",{}).get("new_strategy_description","") or "")[:60].lower().strip()
        if key and key not in seen:
            seen.add(key); dedup += 1
            by_cat_dedup[c.get("paper_category") or c.get("llm_category") or "Unknown"] += 1

    print(f"\n{'='*65}\nRQ4 — {M['ollama']}\n{'='*65}")
    print(f"Analyzed {len(novel)} | new {len(genuinely_new)} | matched {len(matches_known)} | "
          f"proposals {len(proposed_new)} | errors {len(errors)}")
    print(f"After 60-char dedup: {dedup}")
    for zc in ["Bad Randomness","Time Manipulation","Short Address"]:
        print(f"  {zc}: {by_cat_dedup.get(zc,0)} dedup'd new")
    if errors:
        print(f"\nRetry failed commits: python3 07_discover.py --model {args.model} --retry-errors")

    with open(REPORT, "w") as f:
        f.write(f"EXTENSION REPORT — {M['ollama']}\n")
        f.write(f"Analyzed {len(novel)} | genuinely new {len(genuinely_new)} | "
                f"dedup {dedup} | proposals {len(proposed_new)} | errors {len(errors)}\n\n")
        f.write(f"Paper: {cfg.PAPER_RESULTS['novel_commits']} non-aligned :: "
                f"{cfg.PAPER_RESULTS['novel_strategies']} strategies\n")
        for cat, n in sorted(by_cat_dedup.items(), key=lambda x:-x[1]):
            f.write(f"  {cat:<30} {n}\n")
    print(f"Saved {OUT}\nReport {REPORT}")

if __name__ == "__main__":
    discover()