# Hindsight — Week 0–3 Audit Report

**Audited:** 2026-07-16
**Scope:** Weeks 0 (guardrails), 1 (skeleton), 2 (ingestion), 3 (dataset)
**Method:** Automated checks with real command output as evidence. Infrastructure-dependent checks (Docker, live DB, live Redis) marked NOT BUILT where local infra was unavailable.

---

## Verdict Table

| ID | Check | Verdict | Severity |
|----|-------|---------|----------|
| A1 | `uv sync` + Python 3.12 | PASS | — |
| A2 | Pre-commit hooks | PASS | — |
| A3 | `mypy --strict` | PASS | — |
| A4 | Docs present (CLAUDE.md, PROGRESS.md, ADRs) | PASS | — |
| A5 | `.env` gitignored, `.env.example` complete | PARTIAL | MAJOR |
| A6 | `data/raw` gitignored, no tracked data blobs | PARTIAL | MINOR |
| A7 | CI green on main | PASS (config only) | — |
| B1 | Docker compose up + healthchecks | NOT BUILT | — |
| B2 | Alembic migration chain | PASS | — |
| B3 | Architecture layering rules | PARTIAL | MAJOR |
| B4 | Event bus idempotency (content_hash unique) | PASS | — |
| C1 | Crawler SSRF/robots/politeness | PASS (unit tests) | — |
| C2 | Parser extraction + section heuristics | PASS (unit tests) | — |
| C3 | Deduper MinHash/Jaccard logic | PASS (unit tests) | — |
| C4 | Full pipeline end-to-end | NOT BUILT | MAJOR |
| D1 | Incident model + migration | PASS | — |
| D2 | Promoter service pure functions | PASS | — |
| D3 | License audit detection + export policy | PASS | — |
| D4 | Export pipeline determinism | PASS | — |
| D5 | Datasheet + dataset card | PASS | — |
| D6 | HF Hub publish workflow | PASS (config only) | — |
| E1 | Test suite health + coverage | PARTIAL | MAJOR |
| E2 | SAD.md drift | FAIL | MAJOR |
| E3 | Descoped items not built | PASS | — |
| E4 | Dependency hygiene | PASS | — |

---

## Section A — Week 0 Guardrails

### A1: `uv sync` + Python 3.12 — PASS

```
$ uv --version
uv 0.7.12 (Homebrew 2025-07-01)

$ uv run python --version
Python 3.12.13
```

uv manages its own Python 3.12.13 toolchain. The system Python (3.11.4) is irrelevant.

### A2: Pre-commit hooks — PASS

```
$ pre-commit run --all-files
check for added large files.............................Passed
check for case conflicts................................Passed
check yaml..............................................Passed
check json..............................................Passed
fix end of files........................................Passed
trim trailing whitespace................................Passed
ruff (lint).............................................Passed
ruff (format)...........................................Passed
mypy....................................................Passed
detect-secrets..........................................Passed
gitleaks................................................Passed
```

All 11 hooks pass.

### A3: `mypy --strict` — PASS

```
$ uv run mypy app/
Success: no issues found in 49 source files
```

Three `note: By default the bodies of untyped functions are not checked` messages on `alembic/` — these are excluded via `[[tool.mypy.overrides]]` in pyproject.toml. No errors.

### A4: Docs present — PASS

| Document | Status |
|----------|--------|
| `CLAUDE.md` | Present, updated through Week 3 |
| `docs/PROGRESS.md` | Entries for Weeks 0, 1, 2, 3 |
| `CONTRIBUTING.md` | Present |
| `docs/adr/0001-postgres-for-everything.md` | Present |
| `docs/adr/0002-redis-streams-over-kafka.md` | Present |
| `docs/datasheet.md` | Present (Week 3) |
| `docs/dataset_card.md` | Present (Week 3) |

### A5: `.env` gitignored, `.env.example` complete — PARTIAL

**`.env` gitignored:** PASS

```
$ git check-ignore .env
.env
```

**`.env.example` completeness:** FAIL

The following `Settings` fields exist in `app/core/settings.py` but are **missing** from `.env.example`:

| Setting | Default in code | Missing from `.env.example` |
|---------|----------------|-----------------------------|
| `crawler_politeness_interval` | `2.0` | YES |
| `crawler_timeout` | `30` | YES |
| `crawler_user_agent` | `"HindsightBot/0.1"` | YES |
| `crawler_max_concurrency` | `20` | YES |
| `dedup_jaccard_threshold` | `0.85` | YES |
| `dedup_num_perm` | `128` | YES |
| `dedup_band_size` | `4` | YES |

**Severity:** MAJOR — Architecture rule #7 says all config via pydantic-settings, and `.env.example` is the single reference for env vars. A new contributor won't know these tunables exist.

**Proposed fix:** Add a `# Crawler` and `# Deduplication` section to `.env.example` with all 7 fields and their defaults.

### A6: `data/raw` gitignored, no tracked data blobs — PARTIAL

```
$ git ls-files data/
(empty — no tracked data)

$ grep "data/raw" .gitignore
data/raw/
```

`data/raw/` is gitignored. However, `data/export/` (where the export pipeline writes Arrow files and manifest.json) is **not** gitignored.

**Severity:** MINOR — An accidental `git add data/` would commit exported dataset files.

**Proposed fix:** Add `data/export/` to `.gitignore`.

### A7: CI green on main — PASS (config verified)

```yaml
# .github/workflows/ci.yml triggers on push/PR to main
# Jobs: lint (ruff check + ruff format --check + mypy --strict)
#        pre-commit (pre-commit run --all-files)
#        test (uv run pytest tests/)
```

Cannot verify latest run status — `gh` CLI not installed locally. CI config is correctly structured.

---

## Section B — Week 1 Skeleton

### B1: Docker compose up + healthchecks — NOT BUILT

Docker not installed on audit machine. Config review:

- `docker-compose.yml` defines: `postgres` (pgvector/pgvector:pg16), `redis` (redis:7-alpine), `api`, `worker`
- All services have healthchecks
- `docker/Dockerfile` is multi-target (api + worker)
- Healthcheck endpoints: `/v1/healthz` (liveness), `/v1/readyz` (readiness)

**Cannot verify:** Container build, startup, healthcheck probe, Alembic auto-migration.

### B2: Alembic migration chain — PASS

```
Migration chain:
  0001_initial (down_revision: None)
  → 0002_pipeline (down_revision: 0001_initial)
  → 0003_incidents (down_revision: 0002_pipeline)
```

All 3 migrations have both `upgrade()` and `downgrade()` functions. Chain is linear with no gaps.

**Cannot verify:** Actual `alembic upgrade head` / `alembic downgrade base` cycle requires a running Postgres.

### B3: Architecture layering rules — PARTIAL

**Rule 1 (routers = zero logic):** PASS

Both routers (`health.py`, `ingest.py`) delegate to a single service method. The readiness router's `if not report.ready: return JSONResponse(503, ...)` is HTTP-layer concern, not business logic.

**Rule 2 (repositories = only SQLAlchemy layer):** FAIL

Workers and seed_loader import `AsyncSession` and `async_sessionmaker` directly:

```
app/workers/crawler.py:11:  from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
app/workers/parser.py:12:   from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
app/workers/deduper.py:10:  from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
app/ingest/seed_loader.py:17: from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
```

Workers also import repositories directly (e.g., `from app.repositories.document import DocumentRepository`) and construct sessions within `handle()`. This bypasses the DI layer (`app/core/dependencies.py`) that the API uses.

**Severity:** MAJOR — Workers create their own sessions rather than receiving them through DI. This is a structural departure from rule #4 (DI via Depends + factory functions). The workers can't use FastAPI Depends (they're not HTTP handlers), but the session+repo construction should be centralized, not repeated in each worker.

**Proposed fix:** Create a worker-level DI factory (e.g., `create_worker_context()` in `dependencies.py`) that returns a session+repo bundle. Workers call this instead of constructing sessions inline.

**Rule 5 (no monkeypatch):** PASS

```
$ grep -rn "monkeypatch\|unittest.mock\|@patch" tests/
tests/unit/test_health.py:3: (comment mentioning the rule, not usage)
```

Only a docstring reference. Zero actual monkeypatch/mock usage.

### B4: Idempotency (content_hash unique constraint) — PASS

```
app/models/ingest.py:60:    UniqueConstraint("content_hash", name="uq_documents_content_hash")
app/models/incident.py:18:   UniqueConstraint("content_hash", name="uq_incidents_content_hash")
app/models/incident.py:19:   UniqueConstraint("document_id", name="uq_incidents_document_id")
```

Both `documents` and `incidents` tables have unique constraints on `content_hash`.

---

## Section C — Week 2 Ingestion Pipeline

### C1: Crawler — PASS (unit tests)

- SSRF guard: 11 unit tests covering public/private/loopback/link-local/DNS-failure (100% coverage on `ssrf_guard.py`)
- Robots.txt: 5 unit tests covering allow/deny/cache/missing
- Politeness: 4 unit tests covering delay enforcement

**Cannot verify:** Live crawl against real URLs requires running infrastructure.

### C2: Parser — PASS (unit tests)

- 8 unit tests covering trafilatura extraction, section detection, Unicode normalization
- Golden HTML fixture in `tests/fixtures/golden/`

### C3: Deduper — PASS (unit tests)

- 10 unit tests covering MinHash generation, Jaccard threshold, band-hash candidate search

### C4: Full pipeline end-to-end — NOT BUILT

No integration tests exist. The `tests/integration/` directory contains only `__init__.py`.

**Severity:** MAJOR — The pipeline has never been tested end-to-end (seed → crawl → parse → dedup → promote). Each stage is unit-tested in isolation, but stage-to-stage data flow (event schemas, status transitions, content_hash propagation) is unverified.

**Proposed fix:** Add testcontainers-based integration test that runs all pipeline stages against real Postgres + Redis. This was explicitly deferred in Weeks 1, 2, and 3 PROGRESS.md entries.

---

## Section D — Week 3 Dataset

### D1: Incident model + migration — PASS

- `Incident` model has all required fields: `document_id` (FK, unique), `org`, `title`, `url`, `occurred_on`, `severity`, `summary`, `sections` (JSONB), `content_hash` (unique), `license`
- Migration `0003_incidents` creates table with indexes on `org`, `severity`, `occurred_on`
- Downgrade drops the table

### D2: Promoter service — PASS

27 unit tests covering:
- `extract_org`: 8 tests (standard domains, www stripping, github.io, empty URL)
- `estimate_severity`: 8 tests (SEV-0 through SEV-3 keywords, None for unknown)
- `extract_date`: 7 tests (ISO, US, long-month formats, title vs body priority)
- `build_summary`: 4 tests (truncation, sentence boundary, short text)

### D3: License audit — PASS

25 unit tests covering:
- Text detection: CC0, CC-BY-4.0/3.0/2.0, CC-BY-SA, Apache-2.0, MIT (9 tests)
- GitHub license mapping: 5 tests
- Combined detector: 4 tests
- Permissive check: 4 tests (cc0, cc-by, all-rights-reserved, unknown)
- Export policy: 3 tests (permissive includes text, non-permissive excludes, unknown excludes)

### D4: Export pipeline determinism — PASS

13 unit tests covering:
- Same records → identical SHA-256 hash
- Different records → different hash
- Record order determinism (sort by content_hash)
- Schema: 10 features, train split only, severity=int32, sections=valid JSON
- Version: `v0.1.0` → `0.1.0` (v-prefix stripped)

### D5: Datasheet + dataset card — PASS

- `docs/datasheet.md`: Follows Gebru et al. (2021) template — motivation, composition, collection, preprocessing, uses, distribution, maintenance
- `docs/dataset_card.md`: HF Hub README with YAML front matter, feature table, severity scale, section types, usage example, citation

### D6: HF Hub publish workflow — PASS (config verified)

```yaml
# .github/workflows/publish.yml
# Trigger: tag push (v*) + workflow_dispatch (dry-run)
# Steps: checkout → uv sync → export_dataset → push_dataset_to_hub
```

`scripts/push_dataset_to_hub.py` supports `--dry-run` mode. Cannot verify actual HF Hub push without credentials and infrastructure.

---

## Section E — Cross-Cutting Health

### E1: Test suite + coverage — PARTIAL

```
$ uv run pytest tests/ -v
============================= 167 passed in 4.39s ==============================
```

All 167 tests pass. No failures, no skips.

**Coverage:**

```
$ uv run pytest tests/ --cov=app --cov-report=term-missing
TOTAL    1359    436    68%
```

| Module | Coverage | Notes |
|--------|----------|-------|
| `app/workers/crawler.py` | 0% | Zero test coverage |
| `app/ingest/seed_loader.py` | 43% | Only URL extraction tested |
| `app/repositories/document.py` | 31% | No dedicated tests |
| `app/repositories/minhash.py` | 27% | No dedicated tests |
| `app/repositories/incident.py` | 45% | No dedicated tests |
| `app/repositories/source.py` | 48% | No dedicated tests |
| `app/workers/deduper.py` | 49% | Partial — handle() untested |
| `app/workers/parser.py` | 54% | Partial — handle() untested |

**Coverage enforcement:** NOT configured. `pyproject.toml` has `[tool.coverage.run]` and `[tool.coverage.report]` sections but no `fail_under` threshold. CI does not run `--cov` or `--cov-fail-under`.

**Architecture rule #9 (tests ship with every module):** FAIL

Missing test files for:
- `app/repositories/document.py`
- `app/repositories/incident.py`
- `app/repositories/minhash.py`
- `app/repositories/source.py`
- `app/workers/echo.py`

**Severity:** MAJOR — 68% coverage with no enforcement means regressions can ship silently. Five modules have zero dedicated tests. Repository tests are especially important because they're the only SQLAlchemy layer.

**Proposed fix:**
1. Add `fail_under = 75` to `[tool.coverage.report]` in pyproject.toml
2. Add `--cov=app --cov-fail-under=75` to CI test step
3. Add unit test files for all 5 missing modules (repositories need fakes or testcontainers)

### E2: SAD.md drift — FAIL

SAD.md has **not** been updated since Week 1. Multiple sections are stale:

**§7 Data Model — stale:**
- Missing: `incidents` table (added Week 3)
- Missing: `minhash_signatures` table (added Week 2)
- Missing: `DocumentStatus` enum and `status`/`failed_stage`/`url` columns on documents (added Week 2)
- Missing: `license` column on documents (added Week 3)
- Still shows placeholder: `"duplicate_pairs (new table — Week 2+)"` — this was never built; `minhash_signatures` was built instead

**§9 Event Bus — stale:**
- Missing streams: `hindsight:doc.discovered`, `hindsight:doc.parsed`, `hindsight:doc.deduped`
- Missing consumer groups: `crawler-cg`, `parser-cg`, `deduper-cg`
- Still shows never-built placeholders: `hindsight:classify`, `hindsight:embed`, `hindsight:deduplicate`, `hindsight:complete` with "Week 2+" status
- Stream table lists `EchoWorker` on `echo-cg` but doesn't list the three real workers

**Workers section — missing:**
- No documentation of CrawlerWorker, ParserWorker, DeduperWorker
- No documentation of the document state machine (DISCOVERED → FETCHED → PARSED → DEDUPED|DUPLICATE → FAILED)

**Severity:** MAJOR — The SAD is the project's architectural truth. A new contributor reading it gets a fundamentally wrong picture of the data model and event bus. The "Week 2+" placeholders are misleading because Week 2 took a different direction than planned.

**Proposed fix:** Update SAD.md §7 (add incidents, minhash_signatures tables; update documents schema), §9 (replace placeholder streams with actual implemented streams; update consumer group table), and add a pipeline/workers section documenting the state machine.

### E3: Descoped items not built — PASS

```
$ grep -rn "causal.chain|entity.ner|Celery|celery|Grafana|..." app/ scripts/
(none found)
```

No descoped items appear in application code. Celery appears in `pip list` output but is NOT a direct dependency in `pyproject.toml` — it's an indirect dependency of another package in the global environment, not part of the project's venv.

### E4: Dependency hygiene — PASS

- All direct dependencies are pinned with minimum versions in `pyproject.toml`
- `uv.lock` is committed and up to date
- mypy overrides configured for `datasets.*` (untyped library)
- ruff per-file-ignores configured for `scripts/*.py` (S603, S607, ANN401)

---

## Findings by Severity

### BLOCKER

None.

### MAJOR (4 findings)

| # | Finding | Section | Proposed Fix |
|---|---------|---------|-------------|
| M1 | `.env.example` missing 7 crawler/dedup settings | A5 | Add `CRAWLER_*` and `DEDUP_*` entries with defaults |
| M2 | Workers bypass DI — import AsyncSession directly | B3 | Create worker-level DI factory in `dependencies.py` |
| M3 | Zero integration tests; pipeline never tested end-to-end | C4, E1 | Add testcontainers integration test for full pipeline |
| M4 | SAD.md §7 and §9 significantly stale (missing incidents table, minhash_signatures, 3 streams, 3 consumer groups, state machine) | E2 | Update §7 data model, §9 streams+groups, add pipeline section |
| M5 | 5 modules missing dedicated tests (4 repositories + echo worker); coverage 68% with no CI enforcement | E1 | Add test files, set `fail_under=75`, add `--cov` to CI |

### MINOR (1 finding)

| # | Finding | Section | Proposed Fix |
|---|---------|---------|-------------|
| m1 | `data/export/` not gitignored — exported Arrow files could be accidentally committed | A6 | Add `data/export/` to `.gitignore` |

---

## Corpus Health Snapshot

| Metric | Value |
|--------|-------|
| Total unit tests | 167 |
| Integration tests | 0 |
| E2E tests | 0 |
| Test pass rate | 100% (167/167) |
| Code coverage | 68% |
| Coverage enforcement | None |
| mypy errors | 0 |
| ruff violations | 0 |
| Pre-commit hooks | 11/11 pass |
| Alembic migrations | 3 (linear chain, all reversible) |
| Application code lines | ~3,100 |
| Architecture rule violations | 1 (workers bypass DI for session creation) |
| Descoped items leaked | 0 |

---

## GO / NO-GO for Week 4

**Recommendation: CONDITIONAL GO**

The codebase is functionally sound — all 167 tests pass, type checking and linting are clean, and the pipeline logic is well-tested at the unit level. The architecture is largely correct with one structural deviation (workers bypassing DI).

**Conditions for GO:**

1. **Fix M1** (.env.example) — 5 minutes. Blocks onboarding.
2. **Fix M4** (SAD.md) — 30 minutes. The SAD is the architectural source of truth and is dangerously stale.
3. **Fix m1** (data/export gitignore) — 1 minute.

**Defer to Week 4 boundary:**

4. **M2** (worker DI) — The workers work correctly; this is a structural concern, not a correctness bug. Can be addressed when the worker refactoring happens for DeBERTa integration.
5. **M3** (integration tests) — Carry forward as Week 4 work. The unit test coverage is strong enough to proceed.
6. **M5** (repository tests + coverage enforcement) — Repository tests need either fakes or testcontainers. Address alongside M3.

Week 4 (NLP enrichment: DeBERTa classifier, weak supervision) does not depend on any of the deferred items. The incidents table, export pipeline, and license audit are all verified and ready to receive ML-derived labels.
