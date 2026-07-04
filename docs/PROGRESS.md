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
