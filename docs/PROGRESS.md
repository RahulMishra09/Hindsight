# Hindsight — Weekly Progress Log

Each entry follows the same template. Fill every section; write "none" rather than omitting.

---

## Template (copy for each new week)

```markdown
## Week N — YYYY-MM-DD to YYYY-MM-DD

### Shipped
- ...

### Cut (descoped this week, not permanently)
- ...

### Carried Over (from previous week)
- ...

### Metrics
- Lines of application code added:
- Test count (unit / integration / e2e):
- Coverage %:
- Open issues closed:

### Risks
- ...
```

---

## Week 0 — 2026-07-04 to 2026-07-04

### Shipped

- Repository skeleton: all package directories with `__init__.py`; non-Python dirs with `.gitkeep`.
- `docs/SAD.md` — full System Architecture Document (20 sections).
- `CLAUDE.md` — root-level AI assistant context with stack, rules, and descoped list.
- `docs/PROGRESS.md` — this file, with weekly template.
- `docs/adr/0001-postgres-for-everything.md` — ADR for single-store PostgreSQL + pgvector.
- `docs/adr/0002-redis-streams-over-kafka.md` — ADR for Redis Streams event bus.
- `pyproject.toml` — uv-managed project with Python 3.12 pin; ruff (line-length 100, isort) and mypy strict configured.
- `uv.lock` — committed lockfile.
- `.pre-commit-config.yaml` — ruff lint+format, mypy, gitleaks, EOF/trailing-whitespace hooks.
- `.gitignore` — Python, Node, `.env`, `data/raw/`, `models/`, `*.onnx`, wandb, `.DS_Store`.
- `.env.example` — all environment variables enumerated with comments.
- `CONTRIBUTING.md` — setup, commit convention, PR expectations.
- `README.md` — project name, pitch, "under construction" notice, badge placeholders.
- `frontend/README.md` — placeholder noting Week 4 scaffold.
- `.editorconfig` — consistent editor settings.
- `.github/workflows/ci.yml` — pre-commit + pytest on every push/PR.
- `.github/workflows/publish.yml` — documented stub for HF Hub releases (Week 3/5).
- `tests/unit/test_sanity.py` — trivial passing test proving CI is not vacuously green.
- All pre-commit hooks pass on the committed codebase.
- CI green on `main`.

### Cut

- none

### Carried Over

- none (Week 0 is the first entry)

### Metrics

- Lines of application code added: 0 (Week 0 is infrastructure only)
- Test count (unit / integration / e2e): 1 / 0 / 0
- Coverage %: N/A (no application code)
- Open issues closed: 0

### Risks

- `gitleaks` hook requires the `gitleaks` binary to be installed on developer machines; document in CONTRIBUTING.md. Low risk: CI installs it automatically.
- `mypy --strict` on an empty codebase passes trivially; enforcing it becomes meaningful in Week 1 when application code arrives.

---

## Week 1 — 2026-07-04

### Shipped

- **docker-compose.yml** + `docker/Dockerfile` — multi-target build (api + worker), postgres:16 with pgvector, redis:7, healthchecks on all services.
- **app/core/settings.py** — pydantic-settings `Settings` class with all env vars from `.env.example`. Cached via `@lru_cache`.
- **app/core/logging.py** — structlog dual-mode rendering (JSON for production, console for dev). stdlib logging routed through structlog.
- **app/core/db.py** — factory functions for async SQLAlchemy engine, sessionmaker, and Redis client. No connections at import time.
- **app/core/dependencies.py** — FastAPI `Depends` factories wiring DB sessions, Redis, Publisher, and HealthService.
- **app/core/app.py** — application factory with async lifespan managing engine + Redis lifecycle.
- **app/main.py** — ASGI entrypoint for `uvicorn app.main:app`.
- **app/models/base.py** — DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin.
- **app/models/ingest.py** — `Source`, `Document`, `IngestJob` ORM models with constraints and indexes. `content_hash` is the idempotency key on documents.
- **alembic/** — env.py wired to async engine; initial migration creating pgvector extension + 3 tables with downgrade path.
- **app/events/streams.py** — stream name constants (`hindsight:ingest.requested`, `hindsight:doc.fetched`) and `dlq_of()` helper.
- **app/events/schemas.py** — versioned Pydantic event models (`IngestRequested`, `DocFetched`) with frozen config.
- **app/events/publisher.py** — thin async wrapper around Redis XADD with event metadata.
- **app/events/consumer.py** — `BaseWorker` ABC: XREADGROUP poll loop, exponential backoff retry (1s/2s/4s + jitter, max 3), DLQ on exhaustion, XAUTOCLAIM reaper for crashed consumers. Generic over event type.
- **app/workers/echo.py** — toy `EchoWorker` consuming `ingest.requested` to prove chassis works.
- **app/workers/__main__.py** — CLI entrypoint with SIGINT/SIGTERM signal handlers.
- **app/api/v1/health.py** — `/v1/healthz` (liveness) and `/v1/readyz` (readiness probes Postgres + Redis).
- **app/schemas/health.py** — `LivenessResponse`, `ComponentStatus`, `ReadinessReport`.
- **app/services/health.py** — readiness orchestration; returns data only (router handles 503).
- **app/repositories/health.py** — `SELECT 1` DB probe (only SQLAlchemy import in the project).
- **CI updated** — separated lint (ruff + mypy) and test jobs, added dependency caching.
- **39 unit tests** across 9 test files covering settings, event schemas, publisher, consumer retry/DLQ/reaper, health, models, logging, and app factory. All tests use fakes — zero monkeypatch.
- **SAD.md updated** — §7 (data model) and §9 (stream names) aligned with implementation.

### Cut

- Integration tests with testcontainers — deferred to Week 2 when real pipeline workers exist.
- Auth (JWT) — explicitly out of scope per brief.

### Carried Over

- none

### Metrics

- Lines of application code added: ~800
- Test count (unit / integration / e2e): 39 / 0 / 0
- Coverage %: not enforced yet (Week 2+)
- Open issues closed: 0

### Risks

- Docker Desktop required on developer machines for `docker compose up`. Not all team members may have it installed. Mitigated: CONTRIBUTING.md updated.
- `psycopg[binary]` added for Alembic sync DSN but offline migration mode uses async DSN — minor inconsistency, not blocking.
- Data model (sources/documents/ingest_jobs) diverges from original SAD conceptual model (incidents/duplicate_pairs). SAD updated to reflect this. ML enrichment columns added in Week 2+ migrations.

---

## Week 2 — 2026-07-13

### Shipped

- **Document state machine** — `DocumentStatus` enum (`DISCOVERED → FETCHED → PARSED → DEDUPED|DUPLICATE → FAILED`) + `failed_stage` column. Alembic migration `0002_pipeline` adds `status`, `failed_stage`, `url` columns to `documents`, creates `minhash_signatures` table.
- **CrawlerWorker** (`app/workers/crawler.py`) — subclasses `BaseWorker[DocDiscovered]`, fetches raw HTML via `httpx.AsyncClient`, enforces SSRF guard (blocks private/loopback/link-local IPs), robots.txt compliance (cached per domain), per-domain politeness (1 req/2s), conditional GET (ETag/Last-Modified), content_hash dedup at fetch time. Emits `DocFetched`.
- **ParserWorker** (`app/workers/parser.py`) — subclasses `BaseWorker[DocFetched]`, extracts clean text via `trafilatura` with `readability-lxml` fallback, NFC unicode normalization, ASCII-ratio language filter (rejects non-English), section heuristics (Impact/Timeline/Root Cause/Lessons Learned). Emits `DocParsed`.
- **DeduperWorker** (`app/workers/deduper.py`) — subclasses `BaseWorker[DocParsed]`, MinHash LSH (datasketch, 128 permutations, band-size 4), Jaccard > 0.85 threshold, persists band hashes + hashvalues in `minhash_signatures` for restart-safe LSH. Emits `DocDeduped`.
- **Seed loader** (`app/ingest/seed_loader.py`) — fetches danluu/post-mortems and hjacobs/kubernetes-failure-stories READMEs, extracts URLs via markdown link regex, deduplicates, creates `Source` + `Document` rows (status=DISCOVERED), emits `DocDiscovered` events. Runnable as `python -m app.ingest`.
- **Admin API** — `POST /v1/ingest/sources` endpoint with `IngestService` orchestrating source creation. DI factories for `SourceRepository`, `DocumentRepository`, `IngestService`.
- **Repositories** — `DocumentRepository` (CRUD, status transitions, count_by_status), `SourceRepository` (CRUD, list_active), `MinHashRepository` (upsert, band-hash candidate search via JSONB `?|` operator).
- **Support modules** — `ssrf_guard.py` (async DNS resolution, blocks RFC 1918/loopback/link-local/reserved), `robots.py` (TTL-cached per-domain `RobotFileParser`), `politeness.py` (per-domain async lock + minimum delay).
- **Pipeline report** (`scripts/pipeline_report.py`) — per-status document counts, DLQ depths, duplicate rate, top failure reasons.
- **Worker CLI** — `python -m app.workers [echo|crawler|parser|deduper]` selects worker type. Each creates the appropriate sessionmaker and Redis client.
- **New event schemas** — `DocDiscovered`, `DocParsed`, `DocDeduped` (frozen, extra=forbid, versioned). New stream constants: `doc.discovered`, `doc.parsed`, `doc.deduped`. New consumer groups: `crawler-cg`, `parser-cg`, `deduper-cg`.
- **New dependencies** — `httpx`, `trafilatura`, `readability-lxml`, `datasketch`, `lxml` (runtime). `hypothesis` (dev).
- **63 new unit tests** (102 total across 18 files) — SSRF guard (11 tests), robots.txt checker (5), politeness limiter (4), seed loader URL extraction (7), ingest service (4), parser helpers + golden HTML (8), deduper MinHash/Jaccard (10), crawler integration tests for politeness/robots/SSRF/conditional-GET (6). All fakes, zero monkeypatch.

### Cut

- Integration test with testcontainers through all three workers — deferred to Week 3 when the full pipeline can be end-to-end tested with real Postgres + Redis.
- `dateparser` for metadata extraction — trafilatura handles basic date extraction; dedicated dateparser deferred.
- Language detection via `fasttext`/`lingua` — ASCII-ratio heuristic sufficient for v1 English-only filtering.

### Carried Over

- none

### Metrics

- Lines of application code added: ~1,400
- Test count (unit / integration / e2e): 102 / 0 / 0
- Coverage %: not enforced yet
- Open issues closed: 0

### Risks

- `trafilatura` extraction quality varies by page structure — some postmortems with heavy JavaScript rendering will fail extraction and land in FAILED status. Acceptable for v1 scale (1,000 docs).
- MinHash LSH band-hash search uses JSONB `?|` operator which scans all rows. Efficient at 1,000 docs; needs a GIN index at 10,000+.
- Politeness limiter is per-process. Multiple crawler workers on the same host effectively halve the politeness interval. Documented as limitation; acceptable for single-process v1 deployment.
- `content_hash` is recomputed at each stage (URL hash → raw HTML hash → normalized text hash). The unique constraint on `content_hash` can cause conflicts if two different URLs produce identical normalized text. The crawler handles this as early dedup.

---

## Week 3 — 2026-07-15

### Shipped

- **Incident model** (`app/models/incident.py`) — `Incident` ORM model with `document_id` FK (unique), `org`, `title`, `url`, `occurred_on` (date), `severity` (smallint, heuristic), `summary`, `sections` (JSONB), `content_hash` (unique), `license` (default `all-rights-reserved`). Alembic migration `0003_incidents` creates the table with indexes on org, severity, occurred_on.
- **IncidentRepository** (`app/repositories/incident.py`) — CRUD + `get_by_document_id`, `get_by_content_hash`, `list_all` (paginated), `count`.
- **Promoter service** (`app/services/promoter.py`) — Pure functions for metadata extraction from documents: `extract_org` (URL domain parsing with subdomain stripping, github.io handling), `estimate_severity` (keyword-based SEV-0 through SEV-3), `extract_date` (ISO/US/long-month date formats), `build_summary` (sentence-boundary truncation at 500 chars).
- **Promotion script** (`scripts/promote.py`) — Batch-promotes DEDUPED documents to incident rows with idempotency (skip existing content_hash).
- **License audit tooling** (`app/services/license_audit.py`) — License detection from text (CC0, CC-BY, Apache, MIT patterns) and GitHub repo license mapping (SPDX identifiers). Export policy engine: `apply_export_policy` pure function gates `full_text` inclusion on permissive license (`is_permissive` check against frozen set). Default `all-rights-reserved` for unknown licenses.
- **Export pipeline** (`scripts/export_dataset.py`) — Builds HuggingFace `DatasetDict` (train split) with features: id, org, title, url, date, severity, sections (JSON), license, full_text (gated by license policy), content_hash. Deterministic sort by content_hash. Version pinned to git tag (v-prefix stripped for semver). SHA-256 manifest (`manifest.json`) for byte-identical reproducibility. Uses Arrow format via `save_to_disk`.
- **Datasheet** (`docs/datasheet.md`) — Full datasheet following Gebru et al. (2021): motivation, composition (field schema), collection process (5-stage pipeline), preprocessing, uses, distribution (per-record license policy), maintenance.
- **Dataset card** (`docs/dataset_card.md`) — HF Hub README with YAML front matter, feature table, severity scale, section types, usage example, license policy, processing pipeline, reproducibility, citation block.
- **Stats generator** (`scripts/dataset_stats.py`) — Reads exported dataset and generates severity/org/license/section distribution tables for the dataset card.
- **HF Hub publish workflow** (`.github/workflows/publish.yml`) — Tag-triggered GitHub Actions workflow: exports dataset, pushes to HF Hub via `huggingface_hub`. Manual `workflow_dispatch` with dry-run option. Push script (`scripts/push_dataset_to_hub.py`) creates repo, uploads folder, tags revision.
- **New dependencies** — `datasets>=3.0.0`, `huggingface-hub>=0.25.0`.
- **65 new unit tests** (167 total across 22 files) — Promoter: org extraction (8), severity heuristic (8), date parsing (7), summary (4). License audit: text detection (9), GitHub mapping (5), combined detector (4), permissive check (4), export policy (3). Export: determinism (3), license policy in export (3), schema validation (7).

### Cut

- Integration tests with testcontainers for the full promote → export flow — deferred until real Postgres is available in CI.
- ML-derived labels (DeBERTa classifier, embeddings) — deferred to Week 4-5 per plan.
- Active annotation loop — out of scope for v1.

### Carried Over

- none

### Metrics

- Lines of application code added: ~900
- Test count (unit / integration / e2e): 167 / 0 / 0
- Coverage %: not enforced yet
- Open issues closed: 0

### Risks

- Severity heuristic is keyword-based (no ML classifier yet); accuracy is limited for edge cases. Acceptable for v0.1 dataset; ML classifier planned for Week 4.
- Org extraction from URL domain is heuristic; CDN-hosted or aggregator pages may be misattributed.
- Date extraction may pick up unrelated dates from document body. Title dates are preferred when available.
- License detection is conservative: defaults to `all-rights-reserved` when no signal found. This means most records will lack `full_text` in the exported dataset until more license signals are added.
- Export determinism depends on stable Arrow serialization; tested with `datasets>=3.0.0` but cross-version determinism is not guaranteed.
