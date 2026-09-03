# 09_report_statistical.py — significance tests for all 5 RQs across models
#   python3 09_report_statistical.py                  # all models found

import os, sys, json, argparse, warnings
from collections import defaultdict
import numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest, proportion_confint
from statsmodels.stats.contingency_tables import mcnemar
from sklearn.metrics import cohen_kappa_score

warnings.filterwarnings("ignore")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc
PR = cfg.PAPER_RESULTS

def load(name): return mc.load_jsonl(os.path.join(cfg.DATA_DIR, name))

_lines = []
def L(s=""): _lines.append(str(s))

def sig(p):
    return "p<0.001" if p < 0.001 else "p<0.01" if p < 0.01 else "p<0.05" if p < 0.05 else "p>=0.05"
def eff_h(h):
    v = abs(h); return "negligible" if v < .2 else "small" if v < .5 else "medium" if v < .8 else "large"
def eff_k(k):
    v = abs(k); return "slight" if v < .2 else "fair" if v < .4 else "moderate" if v < .6 else "substantial" if v < .8 else "almost perfect"
def eff_d(d):
    v = abs(d); return "negligible" if v < .2 else "small" if v < .5 else "medium" if v < .8 else "large"

def kappa_boot(yt, yp, B=2000, seed=42):
    k = cohen_kappa_score(yt, yp)
    rng = np.random.default_rng(seed); idx = np.arange(len(yt)); boot = []
    for _ in range(B):
        s = rng.choice(idx, len(idx), replace=True)
        a = [yt[i] for i in s]; b = [yp[i] for i in s]
        if len(set(a)) > 1 and len(set(b)) > 1:
            try: boot.append(cohen_kappa_score(a, b))
            except Exception: pass
    lo = np.percentile(boot, 2.5) if boot else float("nan")
    hi = np.percentile(boot, 97.5) if boot else float("nan")
    return k, lo, hi

def present(models):
    return [m for m in models if os.path.exists(os.path.join(cfg.DATA_DIR, f"classified_{m}.jsonl"))]

def rq1(models):
    L("=" * 72); L("RQ1 — CLASSIFICATION: accuracy vs human ceiling + kappa vs 0.72"); L("=" * 72)
    ceiling = PR["human_obs_agreement"]; N = PR["valid_label_set"]
    L(f"H0: LLM accuracy = human observed agreement {ceiling:.4f} (91.76%).")
    L(f"Accuracy denominator fixed at paper's |C_l| = {N}. Two-tailed z, alpha=0.05.")
    L("")
    L(f"  {'Model':<12}{'correct':>8}{'acc':>8}{'95% CI':>18}{'z':>9}{'p':>10}{'h':>8}{'effect':>11}")
    L("  " + "-" * 84)
    for m in models:
        rows = load(f"classified_{m}.jsonl")
        labeled = [r for r in rows if r.get("paper_category", "Unknown") != "Unknown"]
        k = sum(1 for r in labeled if r.get("categories_match"))
        acc = k / N
        lo, hi = proportion_confint(k, N, 0.05, "wilson")
        z, p = proportions_ztest(k, N, value=ceiling)
        h = 2 * (np.arcsin(np.sqrt(acc)) - np.arcsin(np.sqrt(ceiling)))
        L(f"  {m:<12}{k:>8}{acc:>8.3f}   [{lo:.3f},{hi:.3f}]{z:>9.3f}{p:>10.4f}{h:>8.3f}{eff_h(h):>11}")
    L("")
    L("  Bootstrap Cohen's kappa (LLM labels vs human ground truth), B=2000:")
    L(f"  benchmark: human labeling kappa = {PR['cohens_kappa_labeling']}")
    for m in models:
        rows = load(f"classified_{m}.jsonl")
        pairs = [(r["paper_category"], r.get("llm_category", "Unknown")) for r in rows
                 if r.get("paper_category", "Unknown") != "Unknown"]
        if len(pairs) < 5:
            L(f"  {m}: too few pairs"); continue
        pp, ll = zip(*pairs)
        k, lo, hi = kappa_boot(list(pp), list(ll))
        d = k - PR["cohens_kappa_labeling"]
        L(f"  {m:<12} kappa={k:.3f} ({eff_k(k)})  95%CI[{lo:.3f},{hi:.3f}]  "
          f"delta vs human={d:+.3f}")
    L("")

def rq2(models):
    L("=" * 72); L("RQ2 — ADHERENCE: alignment vs 60.55% + kappa vs 0.77 + McNemar"); L("=" * 72)
    base = PR["alignment_percentage"] / 100
    L(f"H0: LLM alignment rate = paper {PR['alignment_percentage']}%. Two-tailed z.")
    L("")
    data = {}
    L(f"  {'Model':<12}{'n':>6}{'aligned':>9}{'rate':>8}{'95% CI':>18}{'z':>9}{'p':>10}{'delta':>9}")
    L("  " + "-" * 82)
    for m in models:
        recs = load(f"aligned_{m}.jsonl") + load(f"novel_{m}.jsonl")
        n = len(recs); k = sum(1 for r in recs if r.get("llm_aligned"))
        rate = k / n if n else 0
        lo, hi = proportion_confint(k, n, 0.05, "wilson")
        z, p = proportions_ztest(k, n, value=base)
        L(f"  {m:<12}{n:>6}{k:>9}{rate:>8.3f}   [{lo:.3f},{hi:.3f}]{z:>9.3f}{p:>10.4f}{rate-base:>+9.3f}")
        data[m] = recs
    L("")
    L("  Bootstrap kappa (LLM adherence vs human ground truth paper_aligned_bool):")
    L(f"  benchmark: human adherence kappa = {PR['cohens_kappa_adherence']}")
    for m in models:
        pairs = [(int(bool(r.get("paper_aligned_bool"))), int(bool(r.get("llm_aligned"))))
                 for r in data[m] if r.get("paper_aligned_bool") is not None]
        if len(pairs) < 5:
            L(f"  {m}: too few pairs"); continue
        pp, ll = zip(*pairs)
        k, lo, hi = kappa_boot(list(pp), list(ll))
        obs = sum(a == b for a, b in zip(pp, ll)) / len(pp)
        L(f"  {m:<12} kappa={k:.3f} ({eff_k(k)})  95%CI[{lo:.3f},{hi:.3f}]  "
          f"obs.agree={obs:.3f}  delta vs human={k-PR['cohens_kappa_adherence']:+.3f}")
    L("")
    L("  McNemar (pairwise: do two models make the same adherence decisions?):")
    ms = list(data.keys())
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            a, b = ms[i], ms[j]
            ma = {r.get("hash"): bool(r.get("llm_aligned")) for r in data[a]}
            mb = {r.get("hash"): bool(r.get("llm_aligned")) for r in data[b]}
            sh = sorted(set(ma) & set(mb))
            if len(sh) < 10:
                L(f"  {a} vs {b}: <10 shared"); continue
            b11 = sum(ma[h] and mb[h] for h in sh)
            b10 = sum(ma[h] and not mb[h] for h in sh)
            b01 = sum(not ma[h] and mb[h] for h in sh)
            b00 = sum(not ma[h] and not mb[h] for h in sh)
            res = mcnemar([[b11, b10], [b01, b00]], exact=(b10 + b01 < 25))
            L(f"  {a} vs {b}: n={len(sh)} only-{a}={b10} only-{b}={b01} "
              f"p={res.pvalue:.4f} ({sig(res.pvalue)})")
    L("")

def rq3(models):
    L("=" * 72); L("RQ3 — QUALITY: LLM mean vs expert 3.80 (one-sample t + Cohen's d)"); L("=" * 72)
    mu0 = PR["overall_expert_mean"]
    L(f"H0: mu_LLM = {mu0}. Two-tailed t, alpha=0.05.")
    L("")
    for m in models:
        recs = load(f"novel_fixes_evaluated_{m}.jsonl")
        if not recs:
            L(f"  {m}: not run"); continue
        sc = [r["llm_evaluation"]["avg_expert_score"] for r in recs
              if isinstance(r.get("llm_evaluation"), dict)
              and r["llm_evaluation"].get("avg_expert_score", 0) > 0]
        if len(sc) < 2:
            L(f"  {m}: too few scores"); continue
        arr = np.array(sc)
        t, p = stats.ttest_1samp(arr, mu0)
        ci = stats.t.interval(0.95, len(arr) - 1, np.mean(arr), stats.sem(arr))
        d = (np.mean(arr) - mu0) / np.std(arr, ddof=1)
        # no-code and scored are not mutually exclusive; report separately
        no_code = sum(1 for r in recs
                      if "No code" in (r.get("llm_evaluation", {}).get("reasoning", "") or ""))
        L(f"  {m}:  n={len(arr)}  mean={np.mean(arr):.3f}  sd={np.std(arr,ddof=1):.3f}")
        L(f"       t({len(arr)-1})={t:.3f}  p={p:.4f} ({sig(p)})  "
          f"95%CI[{ci[0]:.3f},{ci[1]:.3f}]  d={d:.3f} ({eff_d(d)})")
        L(f"       (no-code-context commits among these: {no_code})")
    L("")

def rq4(models):
    L("=" * 72); L("RQ4 — DISCOVERY: zero-literature rate vs coin-flip (H0 p=0.5)"); L("=" * 72)
    ZERO = ["Bad Randomness", "Time Manipulation", "Short Address"]
    for m in models:
        recs = load(f"llm_discovered_fixes_{m}.jsonl")
        if not recs:
            L(f"  {m}: not run"); continue
        L(f"  {m}:")
        for zc in ZERO:
            sub = [r for r in recs if (r.get("paper_category") or "").lower() == zc.lower()]
            if not sub:
                L(f"    {zc:<20}: no commits"); continue
            new = sum(1 for r in sub if r.get("discovery_type") == "new_strategy")
            n = len(sub); rate = new / n
            if new in (0, n):
                L(f"    {zc:<20}: {new}/{n} = {rate:.1%}  (0-variance: z undefined, "
                  f"rate is {'all-novel' if new==n else 'none-novel'})")
            else:
                z, p = proportions_ztest(new, n, value=0.5)
                L(f"    {zc:<20}: {new}/{n} = {rate:.1%}  z={z:.3f} p={p:.4f} ({sig(p)})")
    L("")

def rq5(models):
    L("=" * 72); L("RQ5 — BLIND AUDIT (descriptive validity check)"); L("=" * 72)
    for m in models:
        recs = load(f"independent_scan_{m}.jsonl")
        if not recs: continue
        n = len(recs)
        def c(q, key, fc=False):
            return sum(1 for r in recs if isinstance(r.get(q), dict)
                       and ((r[q].get(key) is False) if fc else bool(r[q].get(key))))
        L(f"  {m} (n={n}): Q1 disputes {c('q1_label_check','label_is_correct',True)} | "
          f"Q2 extra {c('q2_missed_vulns','additional_vulns_found')} | "
          f"Q2 regress {c('q2_missed_vulns','fix_introduces_new_vuln')} | "
          f"Q4 beyond-DASP {c('q4_beyond_dasp','beyond_dasp_pattern_found')}")
    L("  (RQ5 is a blind validity check; Q4 counts are raw flags — see noise-filtered report.)")
    L("")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["7b", "14b", "deepseek"])
    a = ap.parse_args()
    models = present(a.models)
    if not models:
        sys.exit("No model outputs found in data/.")
    L("#" * 72); L("# STATISTICAL REPORT — LLM replication of Salzano et al. (2026)")
    L(f"# Models: {', '.join(models)}  |  all tests two-tailed, alpha=0.05")
    L("#" * 72); L("")
    rq1(models); rq2(models); rq3(models); rq4(models); rq5(models)
    text = "\n".join(_lines)
    print(text)
    os.makedirs(cfg.RESULTS_DIR, exist_ok=True)
    out = os.path.join(cfg.RESULTS_DIR, "statistical_report.txt")
    with open(out, "w") as f: f.write(text)
    print(f"\n[Saved] {out}")

if __name__ == "__main__":
    main()