#!/usr/bin/env python3
# rebuild_diffs.py — replace the [HTTP 401] junk in raw_commits_with_diffs.jsonl
# with REAL diffs from the paper's mining/commit_post_fix.csv, joined on commit hash.
#
# Usage:
#   python3 rebuild_diffs.py
# Writes: data/raw_commits_with_diffs.jsonl  (backs up the old one first)
import os, sys, json, csv
from collections import defaultdict

csv.field_size_limit(10**9)  # diff fields are large

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config_00 as cfg

# locate inputs
JSONL = os.path.join(cfg.DATA_DIR, "raw_commits_with_diffs.jsonl")
CSV_CANDIDATES = [
    os.path.join(cfg.REPO_PATH, "Smart-contract_Vuln",
                 "Smart-Contract-Vulnerabilities-A-Comparative-Study-of-Academic-and-Developer-Solutions-main",
                 "mining", "commit_post_fix.csv"),
    os.path.join(cfg.REPO_PATH, "mining", "commit_post_fix.csv"),
]
CSV_PATH = next((p for p in CSV_CANDIDATES if os.path.exists(p)), None)
if not CSV_PATH:
    sys.exit("commit_post_fix.csv not found. Edit CSV_CANDIDATES with its path.")
print(f"Reading diffs from: {CSV_PATH}")

# group diffs by hash (a commit may touch multiple files -> concatenate)
diffs_by_hash = defaultdict(list)
with open(CSV_PATH, newline="", encoding="utf-8", errors="replace") as f:
    for row in csv.DictReader(f):
        h = (row.get("commit_hash") or "").strip()
        d = (row.get("diff") or "").strip()
        fname = (row.get("file") or "").strip()
        if h and d and not d.startswith("[HTTP"):
            block = (f"--- File: {fname} ---\n{d}" if fname else d)
            diffs_by_hash[h].append(block)
print(f"Commits with real diff in CSV: {len(diffs_by_hash)}")

# join onto the existing jsonl (preserve all paper labels)
rows = []
with open(JSONL, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))
print(f"Commits in jsonl: {len(rows)}")

matched, still_empty = 0, []
for r in rows:
    h = (r.get("hash") or "").strip()
    blocks = diffs_by_hash.get(h)
    if blocks:
        r["diff"] = "\n\n".join(blocks)
        r["files_changed"] = len(blocks)
        matched += 1
    else:
        r["diff"] = r.get("diff", "")  # leave as-is (may still be junk)
        still_empty.append(h)

# validation: check for REAL solidity/diff content, not just non-empty
def looks_real(d):
    d = d or ""
    if len(d) < 30 or d.startswith("[HTTP"):
        return False
    markers = ("@@", "function", "require", "pragma", "contract",
               "modifier", "uint", "address", "mapping", "+ ", "- ")
    return any(m in d for m in markers)

real = sum(1 for r in rows if looks_real(r.get("diff", "")))
print(f"\nJoined real diffs onto {matched}/{len(rows)} commits.")
print(f"Rows passing REAL-content validation: {real}/{len(rows)}")
if still_empty:
    print(f"WARNING: {len(still_empty)} commits had no diff in the CSV, e.g. {still_empty[:3]}")

# back up and write
backup = JSONL + ".http401_backup"
if not os.path.exists(backup):
    os.rename(JSONL, backup)
    print(f"\nBacked up old (junk) file -> {backup}")
else:
    print(f"\nBackup already exists at {backup}; overwriting jsonl only.")

with open(JSONL, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(f"Wrote corrected {JSONL}")

# show a sample so the user can eyeball real code
sample = next((r for r in rows if looks_real(r.get("diff", ""))), None)
if sample:
    print(f"\nSAMPLE ({sample['hash'][:10]}): diff len={len(sample['diff'])}")
    print(sample["diff"][:400])
print(f"\nDONE. If REAL-content count is ~{len(rows)}, rerun RQ1/RQ2/RQ4/RQ5.")