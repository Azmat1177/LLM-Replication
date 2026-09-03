
## 1. What this study does

This is a methodological replication study: We replicate the human-expert annotation study of Salzano et al. (2026) to test
whether large language models can validly substitute for human annotators in empirical
software engineering. Using the same 364 real Solidity vulnerability-fixing commits and
the same expert ground truth, we evaluate six models on five tasks and measure
agreement with **chance-corrected** statistics (Cohen's kappa) rather than raw rates.

The headline finding is a **dissociation**: LLMs match or exceed human inter-rater
reliability on convergent *classification* (kappa up to 0.946 vs. a human 0.72), but
fail on relational *adherence judgement* (kappa plateaus at approx. 0.27 vs. a human
0.77), and this failure does not improve with model scale. We further show that
aggregate agreement rates are an unsound proxy for annotation validity.

---

## 2. Reference dataset

This work builds on the dataset and expert annotations of:

> Salzano et al. (2026). *Bridging the gap: a comparative study of academic and developer approaches to smart contract vulnerabilities*. Empirical Software Engineering.
> DOI: 10.1007/s10664-025-10780-5
> Replication package: https://zenodo.org/records/17105939

The 364-commit corpus, the DASP-10 consensus labels, the adherence flags, and the
nine category-level remediation strategies in reference Table 2 originate there. We
redistribute only the derived artefacts required to reproduce our analysis; the
original dataset should be obtained from the link above.

---

## 3. Package contents

```
.
├── README.md                       this file         
├── requirements.txt                
│
├── scripts/               the evaluation pipeline
│   ├── config_00.py                
│   ├── model_config.py           
│   ├── config_deepseek.py       
│   ├── rebuild_diffs.py          
│   ├── 04_classify.py              
│   ├── 05_compare_fixes.py         
│   ├── 06_eval_novel_fixes.py      
│   ├── 07_discover.py              
│   ├── 08_independent_scan.py      
│   ├── 09_report_descriptive.py    
│   └── 09_report_statistical.py    
│
└── data/                           inputs and raw model outputs
    ├── raw_commits_with_diffs.jsonl        
    ├── novel_fixes.jsonl                
    ├── classified_<model>.jsonl           
    ├── aligned_<model>.jsonl              
    ├── novel_<model>.jsonl                
    ├── novel_fixes_evaluated_<model>.jsonl 
    ├── llm_discovered_fixes_<model>.jsonl  
    └── independent_scan_<model>.jsonl      
```

`<model>` is one of: `7b`, `14b`, `qwen32b`, `deepseek`, `deepseek32b`, `deepseek70b`.

**where this needs to live.** `config_00.py` is working
directories to `~/smart-contract-eval/{repo,data,results,logs}`, resolved from the
user's home directory, not from wherever this package is cloned. Either clone this
package directly to `~/smart-contract-eval/`, or copy `scripts/` into
`~/smart-contract-eval/scripts/` and this package's `data/` into
`~/smart-contract-eval/data/`. `results/` and `logs/` are created automatically the
first time a script runs.

---

## 4. The models

| Registry key   | Model                | Params | Family    | Temp. | num_predict |
|----------------|-----------------------|--------|-----------|-------|-------------|
| `7b`           | Qwen2.5-Coder-7B     | 7.6 B  | code      | 0.0/0.1 | task-dependent |
| `14b`          | Qwen2.5-Coder-14B    | 14.8 B | code      | 0.0/0.1 | task-dependent |
| `qwen32b`      | Qwen2.5-Coder-32B    | 32 B   | code      | 0.0/0.1 | task-dependent |
| `deepseek`     | DeepSeek-R1-7B       | 7 B    | reasoning | 0.6   | 2048        |
| `deepseek32b`  | DeepSeek-R1-32B      | 32 B   | reasoning | 0.6   | 2048        |
| `deepseek70b`  | DeepSeek-R1-70B      | 70 B   | reasoning | 0.6   | 2048        |

All models are Q4_K_M quantised and served locally via Ollama. No commercial API is
used. Sampling is **per task**, not global: classification and adherence (Tasks A, B)
run Qwen greedily at T=0.0; scoring, discovery, and scanning (Tasks C, D, E) run at
T=0.1. DeepSeek-R1 runs at T=0.6 throughout with a 2048-token budget, its `<think>`
reasoning traces are counted against the generation budget, and a smaller budget
truncates the terminating JSON, producing spurious parse failures. See the paper's
Implementation section for the full per-task configuration table.

> The paper's headline six-model comparison and kappa figures cover `7b`,
> `14b`, `qwen32b`, `deepseek`, `deepseek32b` and `deepseek70b` is included
---

## 5. Requirements and setup

### 5.1 Software

- Python 3.12+
- [Ollama](https://ollama.com) with the six models pulled:
  ```bash
  ollama pull qwen2.5-coder:7b
  ollama pull qwen2.5-coder:14b
  ollama pull qwen2.5-coder:32b
  ollama pull deepseek-r1:7b
  ollama pull deepseek-r1:32b
  ollama pull deepseek-r1:70b    
  ```
- A CUDA GPU is recommended. The full 6-model x 5-task matrix over 364 commits
  completes in under three hours on a single GPU; CPU execution is possible but slow.

### 5.2 Get the dataset

A Zenodo record page is not a git repository, `git clone` against it will fail
with "repository not found." Download the record's files instead:

```bash
mkdir -p ~/smart-contract-eval/repo
cd ~/smart-contract-eval/repo

# Option A — browser: visit https://zenodo.org/records/17105939,
# download each file manually, and unzip into this directory.

# Option B — command line, via the Zenodo REST API:
curl -s https://zenodo.org/api/records/17105939 \
  | python3 -c "import json,sys,urllib.request; \
      files=json.load(sys.stdin)['files']; \
      [urllib.request.urlretrieve(f['links']['self'], f['key']) for f in files]"
```

Confirm you now have `relevant_commits.csv`, `new_fixes.json`, and
`mining/commit_post_fix.csv` (needed by the diff-rebuild step, §6.2).

### 5.3 Python dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` pins: `requests`, `tqdm` (used by every task script to call
Ollama and show progress), and `numpy`, `scipy`, `statsmodels`, `scikit-learn`
(used only by `09_report_statistical.py` for bootstrapped Cohen's kappa, z/t-tests,
and McNemar's test).

---

## 6. Reproducing the study

### 6.1 verify the published numbers

The raw model outputs are included, so you can confirm every claim in the paper
**without re-running any inference**:

This re-derives, from the raw JSONL files, every number in the paper, dataset counts,
all six models' RQ1-RQ5 results, the bootstrap-independent statistics, the McNemar
shared-set accounting, the RQ3 distinct-score counts, the RQ4 normalised rates and the
27-strategy arithmetic, and the per-task configuration, and prints PASS/FAIL for each.
It exits 0 when all checks pass.

### 6.2 Re-running inference from scratch

```bash
cd scripts/

# 0. (only if data/raw_commits_with_diffs.jsonl or data/novel_fixes.jsonl are
#    missing, this package ships them pre-built) rebuild the dataset JSONL
#    from the raw Zenodo files:
python3 02_load_dataset.py

# 1. (once) reconstruct diffs from the reference corpus
python3 rebuild_diffs.py

# 2. run each task for each model 
for M in 7b 14b qwen32b deepseek deepseek32b deepseek70b; do
  python3 04_classify.py         --model $M
  python3 05_compare_fixes.py    --model $M
  python3 06_eval_novel_fixes.py --model $M
  python3 07_discover.py         --model $M
  python3 08_independent_scan.py --model $M
done

# 3. generate reports across all six models 
python3 09_report_descriptive.py --models 7b 14b qwen32b deepseek deepseek32b deepseek70b
python3 09_report_statistical.py --models 7b 14b qwen32b deepseek deepseek32b deepseek70b
```

Every task is idempotent: outputs are keyed by commit hash and deduplicated on restart,
so an interrupted run resumes without double-counting. Pass `--fresh` to any task
script to discard that model's existing output and start over, and `--sample N` to
smoke-test on the first N commits before committing to a full run.

`08_independent_scan.py` prints, on completion, the command for an optional
follow-up, noise-filtered report: `python3 10_independence_vuln_report.py -i
<scan file> -o <report path> -m <model>`.

---

## 7. Notes on reproducibility and known conventions

These are documented so that a re-runner is not surprised; none affects the study's
conclusions.

- **Determinism.** Tasks A and B run Qwen at T=0.0 (greedy). Re-running Task B for
  Qwen-14B reproduces a byte-identical partition, confirming the serving stack
  introduces no nondeterminism. This does not test sampling variance, which does not
  arise at T=0.0. The DeepSeek models run at T=0.6 and are therefore stochastic.

- **Duplicate commit hashes.** The reference corpus contains 29 records whose commit
  hash duplicates another (the original mining deduplicated only within a repository,
  so commits mirrored across repositories coexist). Rate and kappa are computed over
  all 364 records; the pairwise McNemar tests key on the commit hash and therefore
  operate on the 335 unique hashes. For the deterministic Qwen models, duplicated
  hashes receive identical decisions; for the stochastic DeepSeek models, 10 (R1-7B)
  and 5 (R1-32B) duplicate pairs received differing decisions, resolved last-write-wins.

- **Guideline granularity.** Task B supplies the reference study's nine category-level
  remediation strategies (their Table 2), which condense their catalogue of 31
  individual guidelines. This is discussed as a construct-validity consideration in
  the paper.

- **Label normalisation.** `raw_commits_with_diffs.jsonl` carries category strings in
  mixed case (e.g. `Reentrancy` and `reentrancy`); the pipeline canonicalises these to
  the DASP-10 labels before scoring. Accuracy is computed over the 352 commits carrying
  a valid label (364 total less 12 annotated *Not Relevant*).

- **Standard deviations** in the quality-scoring table are sample standard deviations
  (ddof=1).

- **Cross-model RQ4 comparisons.** Raw "genuinely new strategy" counts from
  `07_discover.py` are only comparable across models after normalising by each
  model's non-aligned pool size from Task B, a model with a larger non-aligned pool
  will mechanically surface more "novel" strategies.

- **`rebuild_diffs.py` backup file.** The script backs up the pre-repair JSONL as
  `raw_commits_with_diffs.jsonl.http401_backup` before overwriting it. This is a
  working artefact of a single machine's repair run, not a deliverable, exclude it
  from any published copy of this package.

---


---

## 9. License

- **Code** (`scripts/`, `verify_paper_claims.py`): MIT License.
- **Derived data** (`data/`): CC BY 4.0, inheriting the terms of the reference dataset
  (Salzano et al., https://zenodo.org/records/17105939).

---


