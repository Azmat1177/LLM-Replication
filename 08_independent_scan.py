# 08_independent_scan.py — RQ5: Blind Independent LLM Audit (unified)
#   python3 08_independent_scan.py --model 7b|14b|deepseek
#
# Q1 label accuracy | Q2 missed vulns | Q3 fix quality | Q4 beyond-DASP
import os, sys, json, time, requests
from collections import defaultdict
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg
import model_config as mc
from tqdm import tqdm

args = mc.get_args("RQ5 — blind independent LLM audit")
M    = mc.MODELS[args.model]
P    = mc.paths(M["suffix"])
OUT  = P["indep_scan"]

def call_llm(prompt, max_tokens=700):
    try:
        r = requests.post(cfg.OLLAMA_URL, json={
            "model": M["ollama"], "prompt": prompt, "stream": False,
            "options": {**cfg.OLLAMA_OPTIONS, "temperature": 0.1, "num_predict": max_tokens, **M.get("opts", {})},
        }, timeout=M["timeout"])
        parsed = mc.extract_json(r.json().get("response", ""))
        return (parsed, None) if parsed else (None, "NO_JSON")
    except requests.exceptions.Timeout:
        return None, "TIMEOUT"
    except Exception as ex:
        return None, f"ERROR: {ex}"

def q1(message, paper_label, url, diff):
    return f"""You are an independent smart contract security auditor.

A research paper classified this commit as: "{paper_label}"
COMMIT MESSAGE: {message}
REPOSITORY:     {url}
CODE DIFF:
{diff}

Assess from the commit message and code. Is "{paper_label}" the correct
primary vulnerability category? If wrong or too narrow, give the correct one.

Respond ONLY with valid JSON:
{{
  "paper_label":      "{paper_label}",
  "label_is_correct": true or false,
  "correct_label":    "<best label>",
  "label_issues":     "<explanation>",
  "confidence":       "<high|medium|low>"
}}"""

def q2(message, eff_label, url, diff):
    return f"""You are a smart contract security researcher doing an independent audit.

Primary vulnerability label: "{eff_label}"
COMMIT MESSAGE: {message}
REPOSITORY:     {url}
CODE DIFF:
{diff}

Identify secondary vulns, root cause vs symptom, patterns outside DASP-10,
and any regression the fix itself might introduce.

Respond ONLY with valid JSON:
{{
  "primary_vuln":               "{eff_label}",
  "additional_vulns_found":     true or false,
  "additional_vulns": [{{"vuln_type":"<t>","severity":"<critical|high|medium|low>","description":"<d>","in_dasp_taxonomy":true}}],
  "root_cause_correct":         true or false,
  "root_cause_analysis":        "<analysis>",
  "fix_introduces_new_vuln":    true or false,
  "fix_regression_description": "<regression or null>",
  "outside_taxonomy_pattern":   "<pattern or null>",
  "confidence":                 "<high|medium|low>"
}}"""

def q3(message, eff_label, url, diff):
    return f"""You are doing an independent security code review.

The developer says this commit fixes: {eff_label}
COMMIT MESSAGE: {message}
REPOSITORY:     {url}
CODE DIFF:
{diff}

Assess: CORRECTNESS, COMPLETENESS, SAFETY (1-5), and whether a bypass exists.

Respond ONLY with valid JSON:
{{
  "fix_is_correct":      true or false,
  "fix_is_complete":     true or false,
  "fix_is_safe":         true or false,
  "correctness_score":   <integer 1-5>,
  "completeness_score":  <integer 1-5>,
  "safety_score":        <integer 1-5>,
  "correctness_notes":   "<one sentence>",
  "completeness_notes":  "<one sentence>",
  "safety_notes":        "<one sentence>",
  "bypass_possible":     true or false,
  "bypass_description":  "<bypass or null>",
  "overall_fix_quality": "<excellent|good|partial|poor|introduces_new_risk|uncertain>"
}}"""

def q4(message, eff_label, url, diff):
    return f"""You are a cutting-edge blockchain security researcher.

DASP TOP 10 was published in 2018. Post-2018 vectors include: flash loan,
oracle manipulation, MEV/sandwich, cross-protocol reentrancy, governance
attack, precision loss, proxy storage collision, initialization attack,
signature replay, donation/inflation, ERC777/ERC1155 callbacks, read-only
reentrancy, permit front-running.

COMMIT MESSAGE: {message}
REPOSITORY:     {url}
CODE DIFF:
{diff}
Primary label:  {eff_label}

Does this commit suggest a pattern NOT adequately covered by DASP-10?

Respond ONLY with valid JSON:
{{
  "dasp_sufficient":           true or false,
  "beyond_dasp_pattern_found": true or false,
  "pattern_name":              "<name or null>",
  "pattern_category":          "<post_2018_known|novel_pattern|dasp_modern_variant|none>",
  "pattern_description":       "<description>",
  "evidence_in_message":       "<evidence>",
  "taxonomy_gap":              "<gap>",
  "confidence":                "<high|medium|low>"
}}"""

def effective_label(paper_label, q1_res):
    if not q1_res:
        return paper_label, False
    if (q1_res.get("label_is_correct") is False
            and q1_res.get("confidence") == "high"
            and q1_res.get("correct_label")):
        return q1_res["correct_label"].lower().strip(), True
    return paper_label, False

def main():
    if args.fresh and os.path.exists(OUT):
        os.remove(OUT); print(f"Fresh run — deleted {OUT}")

    commits = mc.load_jsonl(mc.RAW_COMMITS)
    if args.sample:
        commits = commits[:args.sample]
    done  = mc.load_done(OUT)
    to_do = [c for c in commits if c.get("hash","") not in done]
    print(f"Model: {M['ollama']} | total {len(commits)} | done {len(done)} | remaining {len(to_do)}")

    errs = defaultdict(int)
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    with open(OUT, "a", buffering=1) as f:
        for c in tqdm(to_do, desc=f"RQ5 [{M['suffix']}]"):
            h   = c["hash"]
            msg = (c.get("message") or "")[:500]
            url = c.get("url", "")
            diff = (c.get("diff") or c.get("pre_fix") or c.get("post_fix") or "")[:1500]
            label = (c.get("dasp_category") or "unknown").strip().lower()
            rec = {"hash": h, "message": msg, "url": url, "paper_label": label,
                   "model": M["ollama"], "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}

            r1, e1 = call_llm(q1(msg, label, url, diff)); rec["q1_label_check"]=r1; rec["q1_error"]=e1
            if e1: errs["q1"]+=1
            eff, corrected = effective_label(label, r1)
            rec["effective_label"]=eff; rec["label_was_corrected"]=corrected

            r2, e2 = call_llm(q2(msg, eff, url, diff)); rec["q2_missed_vulns"]=r2; rec["q2_error"]=e2
            if e2: errs["q2"]+=1
            r3, e3 = call_llm(q3(msg, eff, url, diff)); rec["q3_fix_quality"]=r3; rec["q3_error"]=e3
            if e3: errs["q3"]+=1
            r4, e4 = call_llm(q4(msg, eff, url, diff)); rec["q4_beyond_dasp"]=r4; rec["q4_error"]=e4
            if e4: errs["q4"]+=1
            f.write(json.dumps(rec)+"\n"); time.sleep(0.05)

    recs = mc.load_jsonl(OUT)
    n = len(recs)
    def cnt(q, key): return sum(1 for r in recs if isinstance(r.get(q),dict) and r[q].get(key))
    q1_disputes = sum(1 for r in recs if isinstance(r.get('q1_label_check'),dict)
                      and r['q1_label_check'].get('label_is_correct') is False)
    print(f"\n{'='*62}\nRQ5 — {M['ollama']}  (records: {n})\n{'='*62}")
    print(f"  Q1 disputes        : {q1_disputes}")
    print(f"  Q2 extra vulns     : {cnt('q2_missed_vulns','additional_vulns_found')}")
    print(f"  Q2 regressions     : {cnt('q2_missed_vulns','fix_introduces_new_vuln')}")
    print(f"  Q4 beyond-DASP     : {cnt('q4_beyond_dasp','beyond_dasp_pattern_found')}")
    if errs: print(f"  Errors per question: {dict(errs)}")
    print(f"\nSaved {OUT}")
    report_path = os.path.join(cfg.RESULTS_DIR, f"independent_scan_report_{M['suffix']}.txt")
    print(f"Report: python3 10_independence_vuln_report.py -i {OUT} -o {report_path} -m {M['ollama']}")

if __name__ == "__main__":
    main()