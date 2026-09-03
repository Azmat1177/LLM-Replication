# 09_report_descriptive.py — descriptive results table across models
#   python3 09_report_descriptive.py                 # all models found

# Reads the unified *_{m}.jsonl outputs. Writes results/descriptive_report.txt.
# Purely descriptive (counts, %, means, gaps). Significance tests live in
# 09_report_statistical.py.
import os, sys, json, argparse
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc

PR = cfg.PAPER_RESULTS

def load(name):  # data/<name>
    return mc.load_jsonl(os.path.join(cfg.DATA_DIR, name))

def parse_args():
    p = argparse.ArgumentParser(description="Descriptive report across models")
    p.add_argument("--models", nargs="+", default=["7b", "14b", "deepseek"],
                   help="which model suffixes to include (default: all three)")
    return p.parse_args()

_lines = []
def L(s=""): _lines.append(str(s))

def present_models(models):
    """Keep only models that actually have a classified_{m}.jsonl on disk."""
    out = []
    for m in models:
        if os.path.exists(os.path.join(cfg.DATA_DIR, f"classified_{m}.jsonl")):
            out.append(m)
        else:
            print(f"  (skipping {m}: no classified_{m}.jsonl found)")
    return out

def rq1(models):
    L("=" * 72); L("RQ1 — VULNERABILITY CLASSIFICATION ACCURACY"); L("=" * 72)
    L(f"Accuracy denominator = paper's valid-label set |C_l| = {PR['valid_label_set']} "
      f"(364 - {PR['not_relevant']} Not-Relevant).")
    L(f"Human inter-rater kappa (labeling, Sec 5.3) = {PR['cohens_kappa_labeling']}  "
      f"(accuracy != kappa; not directly comparable).")
    L("")
    hdr = f"  {'Model':<12}{'records':>9}{'valid':>7}{'correct':>9}{'Acc/352':>9}{'Acc/valid':>11}"
    L(hdr); L("  " + "-" * (len(hdr) - 2))
    per_cat = {}
    for m in models:
        rows = load(f"classified_{m}.jsonl")
        labeled = [r for r in rows if r.get("paper_category", "Unknown") != "Unknown"]
        correct = sum(1 for r in labeled if r.get("categories_match"))
        acc352 = correct / PR["valid_label_set"] * 100
        accval = correct / len(labeled) * 100 if labeled else 0
        L(f"  {m:<12}{len(rows):>9}{len(labeled):>7}{correct:>9}{acc352:>8.1f}%{accval:>10.1f}%")
        cd = defaultdict(lambda: [0, 0])
        for r in labeled:
            c = r["paper_category"]; cd[c][0] += 1
            if r.get("categories_match"): cd[c][1] += 1
        per_cat[m] = cd
    L("")
    L(f"  NOTE: 'Acc/352' uses the paper's fixed denominator (your reported figure).")
    L(f"        'Acc/valid' uses each run's actual valid-label count; the small")
    L(f"        gap (e.g. 351 vs 352) reflects commits that normalised to Unknown.")
    L("")
    L("  Per-category recall (correct / paper N):")
    L(f"  {'Category':<26}{'PaperN':>7}" + "".join(f"{m:>10}" for m in models))
    L("  " + "-" * (33 + 10 * len(models)))
    for cat in cfg.DASP_CATEGORIES[:-1]:
        pn = PR["commits_by_category"].get(cat, 0)
        cells = ""
        for m in models:
            n, c = per_cat[m].get(cat, [0, 0])
            cells += f"{(str(round(c/n*100))+'%') if n else 'N/A':>10}"
        L(f"  {cat:<26}{pn:>7}{cells}")
    L("")

def rq2(models):
    L("=" * 72); L("RQ2 — LITERATURE ADHERENCE AGREEMENT"); L("=" * 72)
    L(f"Paper baseline alignment (stated) = {PR['alignment_percentage']}%  "
      f"(221/364; recomputed {PR['alignment_percentage_recalc']}%).")
    L(f"Human inter-rater kappa (adherence, Sec 6.1) = {PR['cohens_kappa_adherence']}.")
    L("")
    hdr = f"  {'Model':<12}{'total':>7}{'aligned':>9}{'novel':>7}{'Align%':>9}{'gap(pp)':>9}"
    L(hdr); L("  " + "-" * (len(hdr) - 2))
    per_cat = {}
    for m in models:
        al = load(f"aligned_{m}.jsonl"); nv = load(f"novel_{m}.jsonl")
        tot = len(al) + len(nv)
        pct = len(al) / tot * 100 if tot else 0
        gap = pct - PR["alignment_percentage"]
        L(f"  {m:<12}{tot:>7}{len(al):>9}{len(nv):>7}{pct:>8.1f}%{gap:>+9.1f}")
        cd = defaultdict(lambda: [0, 0])  # [aligned, total]
        for r in al + nv:
            c = r.get("paper_category") or "Unknown"
            if c != "Unknown":
                cd[c][1] += 1
                if r.get("llm_aligned"): cd[c][0] += 1
        per_cat[m] = cd
    L("")
    L("  Per-category adherence (LLM aligned / total) vs paper rate:")
    L(f"  {'Category':<26}{'Paper%':>8}" + "".join(f"{m:>10}" for m in models))
    L("  " + "-" * (34 + 10 * len(models)))
    for cat in cfg.DASP_CATEGORIES[:-1]:
        pp = PR["adherence_by_category"].get(cat, 0)
        cells = ""
        for m in models:
            a, t = per_cat[m].get(cat, [0, 0])
            cells += f"{(str(round(a/t*100))+'%') if t else 'N/A':>10}"
        L(f"  {cat:<26}{pp:>7.0f}%{cells}")
    L("")

def rq3(models):
    L("=" * 72); L("RQ3 — NOVEL FIX QUALITY SCORING vs EXPERT PANEL"); L("=" * 72)
    L(f"Paper expert mean = {PR['overall_expert_mean']} (N={PR['novel_source_commits']} "
      f"source commits, {PR['expert_panel_size']}-expert panel).")
    L("")
    hdr = f"  {'Model':<12}{'scored':>8}{'no_code':>9}{'LLM mean':>10}{'gap':>8}"
    L(hdr); L("  " + "-" * (len(hdr) - 2))
    for m in models:
        recs = load(f"novel_fixes_evaluated_{m}.jsonl")
        if not recs:
            L(f"  {m:<12}  (not run)"); continue
        scores, no_code = [], 0
        for r in recs:
            ev = r.get("llm_evaluation", {}) or {}
            s = ev.get("avg_expert_score", 0)
            if s and s > 0: scores.append(s)
            if "No code" in (ev.get("reasoning", "") or ""): no_code += 1
        mean = sum(scores) / len(scores) if scores else 0
        gap = mean - PR["overall_expert_mean"]
        L(f"  {m:<12}{len(scores):>8}{no_code:>9}{mean:>10.2f}{gap:>+8.2f}")
    L("")

def rq4(models):
    L("=" * 72); L("RQ4 — NOVEL STRATEGY DISCOVERY"); L("=" * 72)
    L(f"Paper: {PR['novel_commits']} non-aligned commits -> {PR['novel_strategies']} strategies.")
    L("")
    hdr = f"  {'Model':<12}{'analyzed':>10}{'new(raw)':>10}{'dedup':>7}"
    L(hdr); L("  " + "-" * (len(hdr) - 2))
    ZERO = {"bad randomness", "time manipulation", "short address"}
    zero_rows = {}
    for m in models:
        recs = load(f"llm_discovered_fixes_{m}.jsonl")
        if not recs:
            L(f"  {m:<12}  (not run)"); continue
        new = [r for r in recs if r.get("discovery_type") == "new_strategy"]
        seen, dedup, zc = set(), 0, defaultdict(int)
        for r in new:
            desc = (r.get("extension_analysis", {}).get("new_strategy_description", "") or "")
            k = desc[:60].lower().strip()
            if k and k not in seen:
                seen.add(k); dedup += 1
                cat = (r.get("paper_category") or "Unknown")
                if cat.lower() in ZERO: zc[cat] += 1
        L(f"  {m:<12}{len(recs):>10}{len(new):>10}{dedup:>7}")
        zero_rows[m] = zc
    L("")
    L("  Zero-literature category strategies (deduplicated):")
    L(f"  {'Category':<26}" + "".join(f"{m:>10}" for m in zero_rows))
    for cat in ["Bad Randomness", "Time Manipulation", "Short Address"]:
        L(f"  {cat:<26}" + "".join(f"{zero_rows[m].get(cat,0):>10}" for m in zero_rows))
    L("")

def rq5(models):
    L("=" * 72); L("RQ5 — BLIND INDEPENDENT AUDIT (Q1-Q4)"); L("=" * 72)
    for m in models:
        recs = load(f"independent_scan_{m}.jsonl")
        if not recs:
            continue
        n = len(recs)
        def c(q, key, false_check=False):
            k = 0
            for r in recs:
                d = r.get(q)
                if isinstance(d, dict):
                    v = d.get(key)
                    if (v is False) if false_check else bool(v): k += 1
            return k
        q1d = c("q1_label_check", "label_is_correct", false_check=True)
        q2e = c("q2_missed_vulns", "additional_vulns_found")
        q2r = c("q2_missed_vulns", "fix_introduces_new_vuln")
        q4b = c("q4_beyond_dasp", "beyond_dasp_pattern_found")
        L(f"  {m} (n={n}):")
        L(f"    Q1 label disputes         : {q1d}  ({q1d/n*100:.1f}%)")
        L(f"    Q2 commits w/ extra vulns : {q2e}  ({q2e/n*100:.1f}%)")
        L(f"    Q2 fix regressions        : {q2r}  ({q2r/n*100:.1f}%)")
        L(f"    Q4 beyond-DASP flagged    : {q4b}  ({q4b/n*100:.1f}%)")
        L(f"    (Q4 is a raw flag; run 10_independence_vuln_report.py for noise-filtered counts)")
    L("")

def main():
    args = parse_args()
    models = present_models(args.models)
    if not models:
        sys.exit("No model outputs found in data/. Run the pipeline first.")
    L("#" * 72)
    L("# DESCRIPTIVE REPORT — LLM replication of Salzano et al. (2026)")
    L(f"# Models present: {', '.join(models)}")
    L("#" * 72); L("")
    rq1(models); rq2(models); rq3(models); rq4(models); rq5(models)
    text = "\n".join(_lines)
    print(text)
    os.makedirs(cfg.RESULTS_DIR, exist_ok=True)
    out = os.path.join(cfg.RESULTS_DIR, "descriptive_report.txt")
    with open(out, "w") as f:
        f.write(text)
    print(f"\n[Saved] {out}")

if __name__ == "__main__":
    main()