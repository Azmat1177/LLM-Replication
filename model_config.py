# model_config.py
# Single source of truth for model selection and file routing.
# Every question script imports this and takes --model {7b,14b,deepseek}.
import os, sys, json, argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg  # reuse OLLAMA_URL, DATA_DIR, RESULTS_DIR, PAPER_RESULTS, etc.

# Model registry
MODELS = {
    "7b": {
        "ollama":  "qwen2.5-coder:7b",
        "suffix":  "7b",
        "timeout": 300,          # seconds per call (300 fixed the 14B silent-timeout bug)
        "is_reasoning": False,   # no <think> blocks
        "opts": {},              # no overrides — behavior unchanged
    },
    "14b": {
        "ollama":  "qwen2.5-coder:14b",
        "suffix":  "14b",
        "timeout": 800,          # 14B is ~2x slower on CPU (raised for headroom)
        "is_reasoning": False,
        "opts": {},              # no overrides — behavior unchanged, keeps 7b/14b comparable
    },
    "deepseek": {
        "ollama":  "deepseek-r1:7b",
        "suffix":  "deepseek",
        "timeout": 900,          # raised from 480: 2048-token budget on CPU needs headroom
        "is_reasoning": True,    # emits <think>...</think> to strip
        "opts": {                # merged LAST in every call_llm — overrides per-call values
            "num_predict": 2048, # <think> tokens count against this; 512/700 truncates R1 output
            "temperature": 0.6,  # R1 loops/repeats at temp 0.0; DeepSeek recommends 0.5-0.7
        },
    },
    "qwen32b": {
        "ollama":  "qwen2.5-coder:32b",
        "suffix":  "qwen32b",
        "timeout": 600,
        "is_reasoning": False,
        "opts": {},
    },
    "deepseek32b": {
        "ollama":  "deepseek-r1:32b",
        "suffix":  "deepseek32b",
        "timeout": 1200,
        "is_reasoning": True,
        "opts": {"num_predict": 2048, "temperature": 0.6},
    },
    "deepseek70b": {
        "ollama":  "deepseek-r1:70b",
        "suffix":  "deepseek70b",
        "timeout": 1800,
        "is_reasoning": True,
        "opts": {"num_predict": 2048, "temperature": 0.6},
    },
}

# Input data: ALWAYS the with-diffs file (raw_commits.jsonl has empty code)
RAW_COMMITS = os.path.join(cfg.DATA_DIR, "raw_commits_with_diffs.jsonl")

# Per-question output filenames, parameterised by suffix
def paths(suffix):
    d = cfg.DATA_DIR
    r = cfg.RESULTS_DIR
    return {
        "classified":  os.path.join(d, f"classified_{suffix}.jsonl"),
        "aligned":     os.path.join(d, f"aligned_{suffix}.jsonl"),
        "novel":       os.path.join(d, f"novel_{suffix}.jsonl"),
        "novel_eval":  os.path.join(d, f"novel_fixes_evaluated_{suffix}.jsonl"),
        "discovered":  os.path.join(d, f"llm_discovered_fixes_{suffix}.jsonl"),
        "indep_scan":  os.path.join(d, f"independent_scan_{suffix}.jsonl"),
        "report_dir":  r,
    }

# Arg parsing shared by all scripts
def get_args(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--model", required=True, choices=list(MODELS.keys()),
                   help="Which model to run: 7b | 14b | deepseek")
    p.add_argument("--fresh",  action="store_true",
                   help="Delete this model's output and restart")
    p.add_argument("--sample", type=int, default=None,
                   help="Process only the first N commits (smoke test)")
    return p.parse_args()

# Robust loaders
def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out

def load_done(path):
    """Set of commit hashes already written, for resume support."""
    done = set()
    for r in load_jsonl(path):
        h = r.get("hash", "")
        if h:
            done.add(h)
    return done

# DeepSeek <think>-block stripping (no-op for Qwen)
import re
_THINK = re.compile(r"<think>.*?</think>", flags=re.DOTALL)

def strip_think(text):
    return _THINK.sub("", text or "").strip()

def extract_json(text):
    """Strip think-block + code fences, then parse the first {...} object."""
    t = strip_think(text).replace("```json", "").replace("```", "").strip()
    s = t.find("{")
    e = t.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            return json.loads(t[s:e])
        except json.JSONDecodeError:
            pass
    return {}


if __name__ == "__main__":
    # Self-check: confirm the input file exists and carries code + tags.
    print(f"Input file: {RAW_COMMITS}")
    rows = load_jsonl(RAW_COMMITS)
    print(f"Rows loaded: {len(rows)}")
    if rows:
        keys = sorted(rows[0].keys())
        print(f"Keys in row 0: {keys}")
        have_code = sum(1 for r in rows
                        if (r.get('diff') or r.get('pre_fix') or r.get('post_fix') or '').strip())
        have_tag  = sum(1 for r in rows if (r.get('dasp_category') or '').strip())
        have_align= sum(1 for r in rows if str(r.get('paper_aligned', '')).strip())
        print(f"rows with code: {have_code}/{len(rows)}")
        print(f"rows with dasp_category: {have_tag}/{len(rows)}")
        print(f"rows with paper_aligned: {have_align}/{len(rows)}")
    for name, m in MODELS.items():
        print(f"  {name:9s} -> {m['ollama']:20s} suffix={m['suffix']}")