# Hindsight — Week 0-5 Audit Report

**Audit date:** 2026-07-20
**Auditor:** Automated verification pass
**Scope:** Weeks 0–5 (bootstrap → DeBERTa classifier)
**Previous audit:** `docs/audit/week0-3_audit.md` (conditional GO for Week 4)

---

## Verdict Table

| ID | Check | Verdict | Notes |
|----|-------|---------|-------|
| R1 | M1 env-var gap fixed | **FAIL** | `CRAWLER_INTERVAL`, `DEDUP_THRESHOLD`, `MINHASH_*` still missing from `.env.example` |
| R2 | M4 SAD.md updated | **FAIL** | Last commit to SAD.md: `2bd6c7b` (Week 1). 5 weeks stale. |
| R3 | m1 `data/export` in .gitignore | **FAIL** | `grep "data/export" .gitignore` → no match |
| R4 | M2 workers import AsyncSession directly | **FAIL** | All 4 workers + `seed_loader.py` import `AsyncSession` directly (arch rule 2 violation) |
| R5 | M3 integration tests exist | **FAIL** | `tests/integration/` and `tests/e2e/` contain zero test files |
| R6 | M5 coverage gate in CI | **FAIL** | No `fail_under` in pyproject.toml, no `--cov` in CI workflow |
| R7 | PROGRESS.md "Carried Over: none" accuracy | **FAIL** | All 6 weeks claim "Carried Over: none" despite M1-M5 being open since Week 1-3 |
| AB1 | Toolchain runs clean | **PASS** | `uv sync` OK, `pre-commit run --all-files` 11/11 pass, `mypy app/` 57 files OK, `mypy ml/` 19 files OK |
| AB2 | No secrets or data in git | **PASS** | `gitleaks` pass, no `data/` tracked, no model weights tracked, `.env` gitignored |
| AB3 | CI green | **PASS-CODE** | `uv run pytest tests/unit/ -v` configured. No `gh` CLI available to verify latest run status. |
| AB4 | Docker compose up | **NOT BUILT** | `docker` not installed on audit machine. Cannot verify containers, migrations, Redis, Postgres. |
| AB5 | Alembic migrations linear | **PASS-CODE** | 4 migrations in linear chain: 0001→0002→0003→0004. Cannot verify against live DB. |
| AB6 | Architecture rules | **PARTIAL** | Rule 2 violated (workers import AsyncSession). Rule 7 violated (`ml/training/config.py` uses YAML). Rules 1,3,4,5,6,8,9 pass. |
| C1-C10 | Pipeline live run | **NOT BUILT** | Docker unavailable. Cannot start Postgres/Redis, run migrations, seed pipeline, or observe worker output. |
| D1-D5 | Weak supervision live | **NOT BUILT** | Requires live DB with incidents. Cannot verify reconcile script or label voter against real data. |
| E1 | Data prep (stratified split) | **PASS-CODE** | Synthetic 50-example test: `stratified_split()` → train=34, val=8, test=8. Correct ratios. |
| E2 | Training config loads | **PASS-CODE** | `TrainingConfig.from_yaml("ml/training/config.yaml")` → model=deberta-v3-base, lr=2e-5, epochs=10 |
| E3 | Training actually ran | **FAIL** | No `models/` directory, no `wandb/` directory, no `thresholds.json` anywhere. Training has never executed. |
| E4 | Evaluator produces report | **PASS-CODE** | Synthetic data → markdown report with per-label P/R/F1, macro-F1=0.1773, ECE, slice metrics |
| E5 | Regression gate functional | **FAIL** | `baseline.json` has all-zero values. Gate can never fail — any model passes. Protection is vacuous. |
| E6 | Golden set built | **FAIL** | `tests/fixtures/golden/` is empty (only `.gitkeep`). No `golden_set.jsonl` exists anywhere. |
| E7 | ONNX export works | **NOT BUILT** | No trained model exists to export. Export script verified at code level only. |
| E8 | ClassifierWorker runs | **FAIL** | Instantiation crashes: `OSError: hindsight-taxonomy-v1 is not a local folder and is not a valid model identifier` |
| E9 | Backfill script works | **NOT BUILT** | Requires trained model + live DB. Neither exists. |
| E10 | HF Hub push (dry-run) | **PASS-CODE** | `_build_bundle()` produces README.md (2,740b) + copies ONNX/JSON/TXT files. Dry-run works. |
| F1 | Test suite green + coverage | **PARTIAL** | 342 tests pass (12.75s). Coverage: **57%** combined. Multiple critical modules at **0%** (see below). |
| F2 | HF Hub artifacts accessible | **FAIL** | Both `RahuL0009/hindsight-corpus` and `RahuL0009/hindsight-taxonomy` return "repo not found" on HF Hub |
| F3 | SAD.md matches reality | **FAIL** | SAD.md still lists placeholder streams (`hindsight:classify`, `hindsight:embed`, `hindsight:deduplicate`, `hindsight:complete`). Actual streams: `doc.parsed`, `doc.deduped`, `doc.classified`. Missing tables: `incident_labels`, `minhash_signatures`. |
| F4 | No descoped items leaked | **PASS** | No causal-chain, NER, Celery, Grafana, graph UI, active-learning, read replicas, or load testing code found. |
| F5 | Dependency health | **PARTIAL** | 488 packages, `torch` = 501 MB, venv = 1.4 GB. `pip-audit` not installed — cannot verify CVEs. |

---

## Findings by Severity

### BLOCKER

| # | Finding | Evidence | Proposed Fix |
|---|---------|----------|--------------|
| B1 | **Docker not available — entire live-infrastructure verification impossible.** Sections C, D, and live portions of E cannot be executed. | `which docker` → not found | Install Docker Desktop. Re-run audit Sections C-G after Docker is available. |
| B2 | **Training has never run.** No `models/` directory, no `wandb/` logs, no `thresholds.json`, no golden set. The entire ML pipeline (Weeks 4-5) has zero live verification. | `ls models/` → No such file directory. `find . -name thresholds.json` → empty. `ls wandb/` → No such file or directory. | Execute full training pipeline: reconcile → train → threshold tune → ONNX export. This is prerequisite for Week 6 embeddings. |
| B3 | **ClassifierWorker crashes on instantiation.** Cannot load model `hindsight-taxonomy-v1` because no model exists locally or on HF Hub. Worker is non-functional. | `TaxonomyClassifier("hindsight-taxonomy-v1")` → `OSError: is not a local folder and is not a valid model identifier` | Train model (B2), then configure worker to point to local model path or push to HF Hub first. |

### MAJOR

| # | Finding | Evidence | Proposed Fix |
|---|---------|----------|--------------|
| M1 | **6 prior-audit findings (M1-M5, m1) unfixed after 2+ additional weeks.** Originally flagged at Week 3. All remain open at Week 5. PROGRESS.md falsely claims "Carried Over: none" every week. | See R1-R7 in verdict table | Create tracking issues for each. Fix M1 (env vars), M4/F3 (SAD.md), m1 (.gitignore), M5 (coverage gate) this week. M2 (AsyncSession in workers) and M3 (integration tests) can be scheduled but must be acknowledged in PROGRESS.md. |
| M2 | **SAD.md is 5 weeks behind reality.** Stream names, table schemas, worker list, and pipeline stages are all wrong. SAD.md describes a Week 1 system; reality is Week 5. | `git log --oneline -- docs/SAD.md` → last touch `2bd6c7b` (Week 1). Streams listed: `hindsight:classify`, `hindsight:embed`, etc. Actual: `doc.parsed`, `doc.deduped`, `doc.classified`. Missing tables: `incident_labels`, `minhash_signatures`. | Full SAD.md rewrite: update ERD, stream topology, worker table, pipeline stages, API endpoints, ML pipeline section. |
| M3 | **Regression gate is vacuous.** `baseline.json` contains all-zero values. The gate formula (`current - baseline >= -threshold`) can never trigger because any non-negative F1 passes against a zero baseline. | `load_baseline("ml/eval/baseline.json")` → `{"macro_f1": 0.0, "per_label_f1": {"config-change": 0.0, ...}}`. Gate passes for ANY input. | After training (B2), run evaluator on test set to produce real baseline. Commit non-zero `baseline.json`. |
| M4 | **Coverage dropped to 57% with zero coverage on critical modules.** Week 3 audit measured 68%. New code in `ml/` and `app/workers/classifier.py` shipped with 0% test coverage. | `pytest --cov` output. Modules at 0%: `classifier.py` worker (51 lines), `incident_label.py` repo (37 lines), `trainer.py` (93 lines), `threshold.py` (52 lines), `run.py` training (90 lines), `run.py` eval (88 lines), `golden_set.py` (44 lines). | Add unit tests for trainer, threshold, golden_set. Add integration test for classifier worker with fake model. Set `fail_under = 60` in pyproject.toml (step toward 70% target). |
| M5 | **Architecture rule 2 violated by all 4 workers.** Workers directly import `AsyncSession` and construct sessions, bypassing the repository layer. | `grep -rn AsyncSession app/workers/` → hits in `classifier.py:10`, `crawler.py:11`, `parser.py:12`, `deduper.py:10` + `seed_loader.py:17` | Refactor workers to accept repository instances, not raw sessions. Workers should call repository methods. |
| M6 | **Architecture rule 7 violated by training config.** `ml/training/config.py` uses `yaml.safe_load()` instead of pydantic-settings. CLAUDE.md explicitly bans YAML config files. | `grep -rn "import yaml" ml/` → `ml/training/config.py:8` | Convert `TrainingConfig` to pydantic-settings `BaseSettings` class with env-var binding. Remove `config.yaml`. |
| M7 | **HF Hub repos do not exist.** Both `RahuL0009/hindsight-corpus` and `RahuL0009/hindsight-taxonomy` return "repo not found." README badges link to 404 pages. | HF Hub API: "Could not find repo" for both. `curl` returns HTTP 401. | Create repos on HF Hub (can be empty/private initially). Push dataset export + trained model after B2 is resolved. |
| M8 | **`test_classifier_worker.py` tests zero worker logic.** All 7 tests verify event schema constants and DocClassified field shapes. The actual `ClassifierWorker.process()` method has 0% coverage. | File is 66 lines. Tests check `DocClassified.event_type == "doc.classified"`, stream/group constants, and field defaults. No test instantiates or calls the worker. | Write tests with a fake/stub model that exercise `process()` flow: dedup skip, classify, label write, event emit. |
| M9 | **Model card has no real metrics.** `push_model_to_hub.py` MODEL_CARD_TEMPLATE contains architecture description but zero actual performance numbers (no F1, no per-label metrics, no dataset size). | Read `scripts/push_model_to_hub.py` MODEL_CARD_TEMPLATE: no `## Results` section, no metric values anywhere in template. | After training (B2), add a `## Results` section with micro/macro-F1, per-label breakdown, and dataset size. Template should pull from evaluation report. |

### MINOR

| # | Finding | Evidence | Proposed Fix |
|---|---------|----------|--------------|
| m1 | **`pip-audit` not installed — CVE scan impossible.** 488 packages (torch alone 501 MB, venv 1.4 GB). Cannot verify no known vulnerabilities. | `pip-audit` command not found | `uv add --dev pip-audit`, add to CI. |
| m2 | **numpy RuntimeWarnings during evaluation.** Division by zero when computing precision/recall on all-zero arrays. Functionally correct (returns 0.0) but noisy. | `pytest` output: 27 warnings, all `RuntimeWarning: invalid value encountered in divide` from `evaluator.py:43-47` | Use `np.divide(..., where=...)` or suppress with `np.errstate(divide='ignore', invalid='ignore')`. |
| m3 | **`.env.example` missing operational variables.** `CRAWLER_INTERVAL`, `DEDUP_THRESHOLD`, `MINHASH_BANDS`, `MINHASH_ROWS` not documented despite being used in worker code. | `grep -E "CRAWLER_|DEDUP_|MINHASH_" .env.example` → no matches | Add missing variables with sensible defaults and documentation comments. |

---

## Data Reality Snapshot

| Artifact | Expected | Actual |
|----------|----------|--------|
| `models/` directory | Trained DeBERTa checkpoints + ONNX export | **Does not exist** |
| `wandb/` directory | Training experiment logs | **Does not exist** |
| `thresholds.json` | Per-label classification thresholds | **Does not exist anywhere in repo** |
| `tests/fixtures/golden/golden_set.jsonl` | Frozen gold-annotated eval set | **Empty directory (only .gitkeep)** |
| `ml/eval/baseline.json` | Real model performance baseline | **All zeros — meaningless** |
| `data/export/` | Exported dataset for HF Hub | **Not verified (not in .gitignore either)** |
| HF `RahuL0009/hindsight-corpus` | Published incident dataset | **Repo does not exist on HF Hub** |
| HF `RahuL0009/hindsight-taxonomy` | Published ONNX model | **Repo does not exist on HF Hub** |

---

## Artifact Scoreboard

| Artifact | Code Exists | Tests Exist | Live-Verified | Shipped |
|----------|:-----------:|:-----------:|:-------------:|:-------:|
| Crawler worker | Yes | Yes (14 tests) | No (no Docker) | No |
| Parser worker | Yes | Yes (18 tests) | No (no Docker) | No |
| Deduper worker | Yes | Yes (15 tests) | No (no Docker) | No |
| Classifier worker | Yes | Schema-only (7 tests, 0% worker coverage) | **Crashes** | No |
| Promoter service | Yes | Yes (12 tests) | No (no Docker) | No |
| Keyword LFs | Yes | Yes (16 tests) | No (no DB) | No |
| LLM LF | Yes | Yes (8 tests) | No (no API key test) | No |
| Label voter | Yes | Yes (12 tests) | No (no DB) | No |
| Training pipeline | Yes | Yes (data: 7, config: 5) | **Never executed** | No |
| Trainer | Yes | **0 tests** | **Never executed** | No |
| Threshold tuner | Yes | **0 tests** | **Never executed** | No |
| Evaluator | Yes | Yes (8 tests) | Code-only | No |
| Regression gate | Yes | Yes (9 tests) | **Vacuous baseline** | No |
| Golden set builder | Yes | **0 tests** | **Never executed** | No |
| ONNX export | Yes | Yes (6 tests, math-only) | **No model to export** | No |
| TaxonomyClassifier | Yes | Yes (13 tests, static-only) | **No model to load** | No |
| HF dataset push | Yes | Yes (implicit via export) | **Repo 404** | No |
| HF model push | Yes | Yes (5 tests) | **Repo 404** | No |
| Backfill classify | Yes | 0 tests | **No model** | No |

**Summary:** 18 artifacts have code. 14 have some tests. **0 are live-verified. 0 have shipped.**

---

## Coverage Breakdown — Critical Zero-Coverage Modules

| Module | Lines | Coverage | Risk |
|--------|------:|:--------:|------|
| `app/workers/classifier.py` | 51 | 0% | Crashes on instantiation; untested |
| `app/repositories/incident_label.py` | 37 | 0% | Label storage untested |
| `ml/training/trainer.py` | 93 | 0% | Core training loop untested |
| `ml/training/threshold.py` | 52 | 0% | Threshold tuning untested |
| `ml/training/run.py` | 90 | 0% | Training entry point untested |
| `ml/eval/run.py` | 88 | 0% | Eval entry point untested |
| `ml/eval/golden_set.py` | 44 | 0% | Golden set builder untested |
| `ml/export/onnx_export.py` | 106 | 18% | Only math helpers tested |
| `app/workers/crawler.py` | 87 | 0% | Entire worker untested |
| `app/ml/classifier.py` | 75 | 49% | Inference methods untested |

**Total zero-coverage lines in critical modules: 542**

---

## GO / NO-GO for Week 6

### Verdict: **NO-GO**

### Rationale

Week 6 plans to build embeddings (bge-base-en-v1.5), semantic search, and retrieval API. These depend on:

1. **A working classifier pipeline** — Week 6 embeds classified incidents. The classifier has never run (B2), crashes on load (B3), and has a vacuous regression gate (M3). There is no trained model, no thresholds, no golden set, and no ONNX artifact.

2. **Live infrastructure** — Embeddings require Postgres+pgvector and Redis Streams running. Docker has never been verified (B1). No integration tests exist (R5/M1-orig).

3. **Accurate documentation** — SAD.md is 5 weeks stale (M2). Developers starting Week 6 work from a document that describes a different system.

4. **Test confidence** — Coverage has regressed from 68% → 57% (M4). 542 lines in critical ML modules have zero tests. The prior audit's 6 findings are all still open.

### Required Before GO

| Priority | Action | Estimated Effort |
|----------|--------|:----------------:|
| **P0** | Install Docker, verify `docker compose up -d` brings Postgres+Redis online | 30 min |
| **P0** | Run full training pipeline: reconcile → train → threshold tune → evaluate → ONNX export | 2-4 hrs |
| **P0** | Commit real `baseline.json` from evaluation output | 10 min |
| **P0** | Build golden set from annotated data | 30 min |
| **P0** | Fix ClassifierWorker to load from local model path | 30 min |
| **P1** | Rewrite SAD.md to match Week 5 reality | 2-3 hrs |
| **P1** | Add missing env vars to `.env.example` (M1/m3) | 15 min |
| **P1** | Add `data/export` to `.gitignore` | 5 min |
| **P1** | Add `fail_under = 60` coverage gate to CI | 15 min |
| **P1** | Write tests for trainer, threshold, golden_set, classifier worker | 3-4 hrs |
| **P2** | Create HF Hub repos (can be empty/private initially) | 15 min |
| **P2** | Push trained model + dataset to HF Hub | 30 min |
| **P2** | Fix PROGRESS.md to honestly track carried-over items | 30 min |
| **P2** | Install `pip-audit`, run CVE scan | 15 min |

**Estimated total to clear P0+P1 blockers: ~1-2 days of focused work.**

### Recommendation

Complete all P0 items and at minimum the SAD.md rewrite (P1) before starting Week 6. The embeddings work will compound existing debt if the classifier foundation is not verified end-to-end first. Acknowledge carried-over items honestly in PROGRESS.md going forward.

---

*End of audit. Awaiting decisions on findings before any fixes are applied.*
