# config_00.py
import os

# Ollama connection
# To switch model: e.g. "deepseek-coder:7b", "llama3:8b", "mistral:7b"

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:14b"
OLLAMA_MODEL = "qwen2.5-coder:7b"

# Model behaviour controls
OLLAMA_OPTIONS = {
    "temperature":    0.1,
    "num_predict":    1024,
    "num_ctx":        4096,
    "num_thread":     10,
    "repeat_penalty": 1.1,
    "top_k":          10,
    "top_p":          0.9,
}

# File paths
BASE_DIR    = os.path.expanduser("~/smart-contract-eval")
REPO_PATH   = os.path.join(BASE_DIR, "repo")          # cloned paper repo
RESULTS_DIR = os.path.join(BASE_DIR, "results")       # final reports
DATA_DIR    = os.path.join(BASE_DIR, "data")          # intermediate jsonl files
LOGS_DIR    = os.path.join(BASE_DIR, "logs")          # run logs


DASP_CATEGORIES = [
    "Reentrancy", "Access Control", "Arithmetic",
    "Unchecked Return Values", "Denial of Service",
    "Bad Randomness", "Front Running", "Time Manipulation",
    "Short Address", "Unknown",
]


PAPER_RESULTS = {
    "total_commits":           364,      # final curated dataset (PDF p.6, Table 4)

    # Valid-label set and human ceiling (PDF p.6 Sec 5.3, p.13 RQ1)
    # 12 = commits marked "Not Relevant" -> excluded.  364 - 12 = 352 valid labels.
    # 30 = raw LABELING inter-rater disagreements (different thing from the 12).
    #      Human observed agreement ceiling = (364 - 30)/364 = 91.76%.
    # These two figures answer different questions; do not conflate them.
    "not_relevant":            12,       # excluded from classification analysis
    "valid_label_set":         352,      # |C_l| = 364 - 12  (accuracy denominator, eq.1)
    "labeling_conflicts":      30,       # raw disagreements resolved by 3rd rater (Sec 5.3)
    "human_obs_agreement":     0.9176,   # (364-30)/364 = 91.76% -> RQ1 z-test ceiling

    "aligned_with_literature": 221,      # commits matching >=1 guideline (PDF p.11)
    # PDF p.11 RQ1 reports 221 (60.55%).  Arithmetically 221/364 = 60.7142%.
    # The paper's 60.55% is therefore slightly off and is NOT a clean rounding of
    # 221/364.  For a faithful replication we benchmark against the figure the paper
    # actually REPORTS (60.55%); the recomputed 60.71% is kept alongside for reference.
    "alignment_percentage":        60.55,   # paper's STATED benchmark (PDF p.11) <- use this
    "alignment_percentage_recalc": 60.71,   # 221/364 recomputed (paper's own figure is off)

    "novel_commits":           143,      # 364 - 221 (PDF p.13)
    "novel_strategies":         27,      # distinct strategies (PDF p.13 Sec 6.2)
    "novel_source_commits":     35,      # commits producing the 27 strategies (Sec 6.2)

    # Cohen's kappa: three DIFFERENT tasks (all confirmed in PDF)
    "cohens_kappa_labeling":   0.72,    # DASP labeling, Sec 5.3 (PDF p.6), 30 conflicts
    "cohens_kappa_adherence":  0.77,    # literature adherence, Sec 6.1 (PDF p.11)
    "cohens_kappa_novel_id":   0.72,    # novel-fix id, Sec 6.2 (PDF p.13), 15 conflicts
    "novel_id_conflicts":      15,      # resolved during novel-fix identification (Sec 6.2)

    # Per-category adherence rates (PDF p.12, Table 5 + RQ1 text)
    "adherence_by_category": {
        "Access Control":          75.00,   # 51/68
        "Reentrancy":              67.95,   # 53/78
        "Arithmetic":              66.08,   # 113/171
        "Unchecked Return Values": 42.86,   # 3/7
        "Front Running":           33.33,   # 1/3
        "Denial of Service":        0.00,   # 0/6
        "Bad Randomness":           0.00,   # 0/6
        "Time Manipulation":        0.00,   # 0/23
        "Short Address":            33.33,   # 1/3  (Table 5, PDF p.12)
    },

    # Commit counts per category (PDF p.12 Table 5; Fig.4 agrees except Short Address)
    "commits_by_category": {
        "Reentrancy":              78,
        "Access Control":          68,
        "Arithmetic":             171,
        "Unchecked Return Values":  7,
        "Denial of Service":        6,
        "Bad Randomness":           6,
        "Front Running":            3,
        "Time Manipulation":       23,
        "Short Address":            3,    # Table 5 = 3; Fig.4 bar = 2 (paper self-conflict).
                                          # Using 3 (Table 5), consistent with "1 out of 3".
    },

    # Table 6 per-fix expert averages, in fix order (PDF p.39 Table 6).
    # 27 values; their mean = 3.7989 ~= the paper's stated overall mean 3.80.
    "table6_avg_scores": [
        3.85, 4.07,                         # Access Control Fix1, Fix2
        3.52, 3.41, 3.89, 4.00,             # Arithmetic Fix1-4
        3.70, 3.96, 3.96, 4.04,             # Arithmetic Fix5-8
        3.82, 3.74,                         # Bad Randomness Fix1-2
        3.71, 3.67, 3.82, 2.96,             # Denial of Service Fix1-4
        3.85, 3.82,                         # Front Running Fix1-2
        3.96, 4.04, 3.93, 3.82, 3.82,       # Reentrancy Fix1-5
        4.04,                               # Short Address Fix1
        3.21, 3.52,                         # Time Manipulation Fix1-2
        4.44,                               # Unchecked Return Values Fix1
    ],

    "expert_panel_size":        9,       # 5 academic + 4 industry (PDF p.33 Sec 7.1)
    "overall_expert_mean":      3.80,    # paper's stated overall mean (PDF p.11 / Table 6)
}


PAPER_NOVEL_AVG = (
    sum(PAPER_RESULTS["table6_avg_scores"]) /
    len(PAPER_RESULTS["table6_avg_scores"])
)   # = 3.7989, reproduces paper's 3.80

PAPER_NOVEL_BY_CAT = {
    "Access Control":          round((3.85 + 4.07) / 2, 2),                          # 3.96
    "Arithmetic":              round((3.52+3.41+3.89+4.00+3.70+3.96+3.96+4.04)/8,2), # 3.81
    "Bad Randomness":          round((3.82 + 3.74) / 2, 2),                          # 3.78
    "Denial of Service":       round((3.71+3.67+3.82+2.96) / 4, 2),                  # 3.54
    "Front Running":           round((3.85 + 3.82) / 2, 2),                          # 3.83
    "Reentrancy":              round((3.96+4.04+3.93+3.82+3.82) / 5, 2),             # 3.91
    "Short Address":           4.04,
    "Time Manipulation":       round((3.21 + 3.52) / 2, 2),                          # 3.37
    "Unchecked Return Values": 4.44,
}

# Literature guidelines (PDF p.10 Table 2). Empty list = zero-literature category:
# Bad Randomness, Time Manipulation, Short Address had NO practical documented fix.
# NOTE: Denial of Service DOES have a guideline ("avoid transfer() in loops") but
# 0% adherence in the data -- it is zero-ADHERENCE, not zero-LITERATURE.
LITERATURE_GUIDELINES = {
    "Reentrancy": [
        "Use NonReentrant modifier from OpenZeppelin",
        "Use send() or transfer() instead of call() [OUTDATED post EIP-1884 -- see Sec 8.2]",
        "Follow Checks-Effects-Interactions pattern",
    ],
    "Access Control":          ["Use OnlyOwner modifier from OpenZeppelin"],
    "Arithmetic":              [
        "Use SafeMath library from OpenZeppelin",
        "Use require statements to check arithmetic operations",
    ],
    "Unchecked Return Values": ["Check return value of low-level calls with require or if"],
    "Denial of Service":       ["Avoid using transfer() in loop statements"],
    "Front Running":           ["Require current allowance to match expected value or be zero"],
    "Bad Randomness":          [],   # zero-literature (PDF p.10 Table 2)
    "Time Manipulation":       [],   # zero-literature
    "Short Address":           [],   # zero-literature
}

# Real CSV column names from relevant_commits.csv
CSV_COLUMNS = {
    "hash":       "Commit",
    "message":    "Message",
    "url":        "URL",
    "category":   "Tag",              # final
    "category1":  "Tag1",             # rater 1
    "category2":  "Tag2",             # rater 2
    "aligned":    "IsInLiteratureTag",
    "aligned1":   "IsInLiteratureTag1",
    "aligned2":   "IsInLiteratureTag2",
    "employable": "IsEmployableFixTag",
    "employable1":"IsEmployableFixTag1",
    "employable2":"IsEmployableFixTag2",
}