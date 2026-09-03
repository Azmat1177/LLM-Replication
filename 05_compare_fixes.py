# 05_compare_fixes.py — RQ2: Literature Adherence (unified)
#   python3 05_compare_fixes.py --model 7b|14b|deepseek
import os, sys, json, time, requests
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc
from tqdm import tqdm

args = mc.get_args("RQ2 — literature adherence")
M    = mc.MODELS[args.model]
P    = mc.paths(M["suffix"])
IN   = P["classified"]
OUT_ALIGNED = P["aligned"]
OUT_NOVEL   = P["novel"]

GUIDELINES_TEXT = "\n".join(
    f"[{cat}]: {'; '.join(fixes) if fixes else 'No documented practical fix in literature'}"
    for cat, fixes in cfg.LITERATURE_GUIDELINES.items()
)

ADHERENCE_PROMPT = """You are evaluating smart contract security fixes against academic literature.

KNOWN ACADEMIC GUIDELINES (from peer-reviewed papers):
{guidelines}

IMPORTANT: The guideline "Use send() or transfer() instead of call()" for Reentrancy
is outdated after EIP-1884 changed gas costs. Do NOT mark a fix as non-aligned solely
because it uses .call() with proper guards.

Developer fix to evaluate:
Category: {category}
Commit message: {message}
Post-fix code:
{post_fix}

Does this fix MATCH any documented academic guideline for "{category}"?

Respond ONLY with valid JSON:
{{
  "adheres_to_literature": true or false,
  "matched_guideline":     "<exact guideline matched, or null>",
  "confidence":            "<high|medium|low>",
  "explanation":           "<one sentence>"
}}"""

def bool_from_paper(raw):
    return str(raw).strip().lower() in ("true", "1", "yes", "aligned", "y")

def call_llm(prompt):
    try:
        r = requests.post(cfg.OLLAMA_URL, json={
            "model":   M["ollama"],
            "prompt":  prompt,
            "stream":  False,
            "options": {**cfg.OLLAMA_OPTIONS, "temperature": 0.0, **M.get("opts", {})},
        }, timeout=M["timeout"])
        return mc.extract_json(r.json().get("response", ""))
    except Exception as ex:
        return {"adheres_to_literature": False, "explanation": str(ex)}

def main():
    if not os.path.exists(IN):
        sys.exit(f"ERROR: {IN} not found. Run 04_classify.py --model {args.model} first.")
    if args.fresh:
        for p in (OUT_ALIGNED, OUT_NOVEL):
            if os.path.exists(p): os.remove(p)
        print("Fresh run — cleared aligned/novel outputs")

    commits = mc.load_jsonl(IN)
    if args.sample:
        commits = commits[:args.sample]

    done = mc.load_done(OUT_ALIGNED) | mc.load_done(OUT_NOVEL)
    to_do = [c for c in commits if c.get("hash", "") not in done]
    print(f"Model: {M['ollama']} | total {len(commits)} | done {len(done)} | remaining {len(to_do)}")

    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    f_al = open(OUT_ALIGNED, "a", buffering=1)
    f_nv = open(OUT_NOVEL,   "a", buffering=1)
    for commit in tqdm(to_do, desc=f"RQ2 [{M['suffix']}]"):
        category = commit.get("paper_category") or commit.get("llm_category", "Unknown")
        post_fix = commit.get("post_fix") or commit.get("diff") or ""
        commit["paper_aligned_bool"] = bool_from_paper(commit.get("paper_aligned", ""))
        adherence = call_llm(ADHERENCE_PROMPT.format(
            guidelines=GUIDELINES_TEXT, category=category,
            message=(commit.get("message") or "")[:200], post_fix=post_fix[:1500],
        ))
        commit["adherence"]   = adherence
        commit["llm_aligned"] = adherence.get("adheres_to_literature", False)
        (f_al if commit["llm_aligned"] else f_nv).write(json.dumps(commit) + "\n")
        time.sleep(0.05)
    f_al.close(); f_nv.close()

    aligned = mc.load_jsonl(OUT_ALIGNED)
    novel   = mc.load_jsonl(OUT_NOVEL)
    total   = len(aligned) + len(novel)
    pct     = len(aligned) / total * 100 if total else 0
    paper_pct = cfg.PAPER_RESULTS["alignment_percentage"]
    print(f"\n{'='*60}\nTASK B — {M['ollama']}\n{'='*60}")
    print(f"Aligned {len(aligned)} | Novel {len(novel)} | Alignment {pct:.1f}% "
          f"(paper {paper_pct:.2f}%, gap {pct-paper_pct:+.1f}pp)")
    with_gt = sum(1 for c in aligned+novel if c.get("paper_aligned_bool") is not None)
    print(f"paper_aligned_bool present: {with_gt}/{total}  -> commit-level kappa computable")
    print(f"\nSaved {OUT_ALIGNED} / {OUT_NOVEL}")
    print(f"Next: 06_eval_novel_fixes.py --model {args.model}  and  07_discover.py --model {args.model}")

if __name__ == "__main__":
    main()