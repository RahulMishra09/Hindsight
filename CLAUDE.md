# Hindsight — AI Assistant Context

**One-liner:** Open incident-intelligence platform: ingest → NLP enrich → semantic search → pattern surfacing.

**Full architecture:** [docs/SAD.md](docs/SAD.md)
**Weekly progress:** [docs/PROGRESS.md](docs/PROGRESS.md)

---

## Stack (pinned — do not upgrade without an ADR)

| Concern | Choice |
|---------|--------|
| Language | Python 3.12 |
| API framework | FastAPI (fully async) |
| ORM | SQLAlchemy 2 async + asyncpg driver |
| Migrations | Alembic |
| Database | PostgreSQL 16 + pgvector extension |
| Event bus | Redis 7 Streams (consumer groups) |
| Classifier model | DeBERTa-v3-base, ONNX int8 |
| Embedding model | bge-base-en-v1.5 (768-dim) |
| Reranker model | ms-marco-MiniLM-L6-v2 cross-encoder |
| Frontend | React 18 + TypeScript + Tailwind CSS + shadcn/ui |
| Package manager | uv |
| Linter/formatter | ruff (line-length 100, isort rules) |
| Type checker | mypy (strict mode) |
| Test runner | pytest + pytest-asyncio |
| Integration tests | testcontainers (real Postgres + Redis) |
| Pre-commit | pre-commit (ruff, mypy, gitleaks, EOF/whitespace hooks) |

---

## Architecture Rules

These rules are **non-negotiable** in every PR. Violating them is a blocker.

1. **Routers contain zero logic.** A router handler calls exactly one service method and returns its result. No DB calls, no business decisions, no conditional branching in routers.

2. **Repositories are the only SQLAlchemy layer.** Nothing outside `app/repositories/` imports `AsyncSession` or constructs queries. Services call repository methods; they do not build queries.

3. **One consumer group per worker type.** Each worker class registers a single named consumer group. Multiple process instances of the same worker share that group for horizontal scaling.

4. **DI via `Depends` + factory functions.** All dependencies (DB sessions, services, repositories) are wired through FastAPI `Depends`. No global singletons, no module-level DB connections.

5. **Tests bind fakes, never monkeypatch.** Integration tests inject `FakeXxxRepository` implementations. `monkeypatch` and `unittest.mock.patch` are banned in unit and integration tests. Only use them in isolated test-utility code if unavoidable.

6. **Every pipeline handler is idempotent on `content_hash`.** Processing a message whose `content_hash` already exists in the DB is a no-op followed by ACK. Never double-process.

7. **All config via `pydantic-settings`.** No hardcoded values, no YAML config files, no `os.getenv()` calls scattered in application code. One `Settings` class in `app/core/settings.py`.

8. **Conventional commits.** Format: `type(scope): description`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`. Scope matches the package or layer modified (e.g., `feat(api): add incident list endpoint`).

9. **Tests ship with every module.** A PR that adds `app/services/foo.py` must include `tests/unit/test_foo.py`. No exceptions.

10. **No application code in Week 0.** This week creates rails only. `grep -r "FastAPI(" app/` must return nothing until Week 1.

---

## Descoped for v1.0 — Do NOT Build

The following items are explicitly out of scope. If you find yourself starting to implement any of these, stop and check the issue tracker.

- **Causal-chain extractor** — requires graph traversal + annotation infrastructure not available in v1
- **Entity NER tagger** — insufficient labelled data; adds inference latency; deferred to v2
- **Celery task queue** — Redis Streams covers throughput needs; Celery adds ops overhead
- **Grafana/Prometheus observability stack** — overkill for v1 single-node; structured JSON logs suffice
- **Graph UI (network visualization)** — blocked on causal-chain extractor
- **Active-learning annotation loop** — requires Prodigy/Label Studio integration; Week 6+
- **Read replicas / replica routing** — single primary sufficient for v1 read load
- **Load testing suite (Locust/k6)** — deferred until post-v1 performance baseline exists

---

## Current Status

See [docs/PROGRESS.md](docs/PROGRESS.md) for the latest weekly entry.

**Current week:** Week 0 (repository bootstrap)
**Next milestone:** Week 1 — Docker Compose, database schema, Alembic baseline, first FastAPI app factory, Redis consumer base class.

---

## Quick Commands

```bash
# Install dependencies
uv sync

# Run linter
uv run ruff check .

# Run formatter
uv run ruff format .

# Run type checker
uv run mypy .

# Run tests
uv run pytest

# Run pre-commit on all files
pre-commit run --all-files
```

---

## Key File Locations

| What | Where |
|------|-------|
| Settings class | `app/core/settings.py` (Week 1) |
| DI factories | `app/core/dependencies.py` (Week 1) |
| SQLAlchemy Base | `app/models/base.py` (Week 1) |
| Alembic env | `alembic/env.py` (Week 1) |
| Redis consumer base | `app/events/consumer.py` (Week 1) |
| ADRs | `docs/adr/` |
| Env var reference | `.env.example` |
