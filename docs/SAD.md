# Hindsight — System Architecture Document

**Version:** 0.1.0-draft
**Date:** 2026-07-04
**Status:** Living document — updated each sprint

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [System Context](#4-system-context)
5. [High-Level Architecture](#5-high-level-architecture)
6. [Component Breakdown](#6-component-breakdown)
7. [Data Model (conceptual)](#7-data-model-conceptual)
8. [API Design Principles](#8-api-design-principles)
9. [Event Bus Design](#9-event-bus-design)
10. [ML Pipeline](#10-ml-pipeline)
11. [Authentication & Authorization](#11-authentication--authorization)
12. [Configuration Management](#12-configuration-management)
13. [Testing Strategy](#13-testing-strategy)
14. [Dependency Injection](#14-dependency-injection)
15. [Error Handling & Idempotency](#15-error-handling--idempotency)
16. [Frontend](#16-frontend)
17. [Deployment Topology (target)](#17-deployment-topology-target)
18. [Repository Layout](#18-repository-layout)
19. [Architecture Decision Records](#19-architecture-decision-records)
20. [Glossary](#20-glossary)

---

## 1. Purpose & Scope

Hindsight is an **open incident-intelligence platform** that ingests raw incident reports, applies NLP enrichment (classification, severity estimation, near-duplicate detection, semantic search), and surfaces actionable patterns through a REST API and a lightweight React dashboard.

The platform is designed to be self-hostable, reproducible, and fully open-source. It ships both a runnable system and the training artefacts (labelled dataset + fine-tuned models) as first-class release deliverables.

---

## 2. Problem Statement

Engineering teams accumulate hundreds to thousands of incident post-mortems but lack tooling to:

- Detect when an incident pattern has occurred before.
- Surface semantically similar past incidents at alert time.
- Measure incident frequency, MTTR, and recurrence rates across a structured corpus.
- Reproduce or audit the ML enrichment pipeline from raw text.

Hindsight solves all four without requiring cloud ML services.

---

## 3. Goals & Non-Goals

### Goals (v1.0)

- Ingest incident text via REST and async pipeline.
- Classify incident type and estimate severity with a fine-tuned DeBERTa-v3-base model (ONNX int8 for CPU inference).
- Detect near-duplicates via MinHash LSH + cosine similarity on bge-base-en-v1.5 embeddings.
- Rank semantically similar incidents via ms-marco-MiniLM-L6-v2 cross-encoder.
- Store structured data in PostgreSQL 16 with pgvector for ANN search.
- Stream pipeline events through Redis 7 Streams (consumer groups per worker type).
- Expose a versioned async REST API (FastAPI, `/api/v1/`).
- Serve a React + TypeScript + Tailwind dashboard (read-only in v1.0).
- Release labelled dataset to Hugging Face Hub (Week 3) and ONNX model (Week 5).
- Green CI on every commit; all code path changes ship with tests.

### Non-Goals (explicitly descoped — do NOT build for v1.0)

See §19 ADR-0003 for rationale on each item.

| Item | Reason descoped |
|------|----------------|
| Causal-chain extractor | Requires graph traversal + complex annotation; deferred to v2 |
| Entity NER tagger | Insufficient labelled data in v1 corpus; adds inference latency |
| Celery task queue | Redis Streams covers our throughput; Celery adds ops overhead |
| Grafana/Prometheus observability stack | Overkill for v1 single-node; structured logs suffice |
| Graph UI (network viz) | Blocked on causal-chain extractor |
| Active-learning annotation loop | Requires Prodigy or Label Studio integration; Week 6+ |
| Read replicas / replica routing | Single primary sufficient for v1 read load |
| Load testing suite (Locust/k6) | Deferred until post-v1 perf baseline exists |

---

## 4. System Context

```
┌─────────────────────────────────────────────────────────────┐
│                        External Actors                       │
│  • Engineers (REST clients, dashboard users)                 │
│  • CI/CD pipeline (automated ingestion)                      │
│  • Hugging Face Hub (model + dataset artefacts)              │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS
                ┌───────────▼───────────┐
                │     Hindsight System   │
                │  (single-node v1.0)    │
                └───────────────────────┘
```

---

## 5. High-Level Architecture

```
┌──────────────┐     HTTP/REST      ┌──────────────────────────┐
│   React SPA  │◄──────────────────►│  FastAPI (async)         │
│  (TS+Tailwind│                    │  /api/v1/                │
└──────────────┘                    └──────────┬───────────────┘
                                               │ async SQLAlchemy 2
                                    ┌──────────▼───────────────┐
                                    │  PostgreSQL 16 + pgvector │
                                    └──────────────────────────┘
                                               │
                                    ┌──────────▼───────────────┐
                                    │  Redis 7 Streams          │
                                    │  (pipeline event bus)     │
                                    └──────────┬───────────────┘
                                               │ consumer groups
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
               ┌──────────▼──────┐  ┌──────────▼──────┐  ┌────────▼────────┐
               │  Classifier     │  │  Embedder        │  │  Deduplicator   │
               │  Worker         │  │  Worker          │  │  Worker         │
               │ (DeBERTa ONNX)  │  │ (bge-base-en)    │  │ (MinHash + ANN) │
               └─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 6. Component Breakdown

### 6.1 API Layer (`app/api/`)

- All request routing and response shaping lives here.
- **Routers contain zero business logic.** A router handler calls exactly one service method and returns its result.
- Input validation via Pydantic v2 schemas (`app/schemas/`).
- Versioned under `/api/v1/`; future versions get their own sub-package.

### 6.2 Core (`app/core/`)

- Application factory, lifespan handlers (startup/shutdown), settings, security utilities.
- `settings.py`: single `Settings` class extending `pydantic-settings BaseSettings`; all config from environment.
- `security.py`: JWT creation/validation (HS256, configurable expiry).

### 6.3 Models (`app/models/`)

- SQLAlchemy 2 declarative mapped classes only.
- No business logic. No classmethods that touch the DB directly.
- `Base` defined here; imported by `alembic/env.py`.

### 6.4 Schemas (`app/schemas/`)

- Pydantic v2 request/response models.
- Separate `Request` and `Response` variants per resource.
- Shared validators live in `app/schemas/common.py`.

### 6.5 Repositories (`app/repositories/`)

- **The only layer that imports SQLAlchemy.**
- One repository class per aggregate root.
- Methods are `async` and accept an `AsyncSession` injected via `Depends`.
- No business logic; only CRUD + query construction.

### 6.6 Services (`app/services/`)

- Orchestration layer: calls repositories, emits Redis events, applies business rules.
- Injected into routers via `Depends` factory functions.
- Tests use fake repositories injected at the factory level — never `monkeypatch`.

### 6.7 Events (`app/events/`)

- Redis Streams publish/consume helpers.
- `publisher.py`: thin async wrapper around `aioredis` XADD.
- `consumer.py`: base consumer class with XREADGROUP + ACK loop.
- Each worker registers **one consumer group**; multiple instances of the same worker share the group.

### 6.8 Workers (`app/workers/`)

- Long-running async consumer processes (not threads, not Celery tasks).
- Each worker subclasses the base consumer and handles exactly one event type.
- Workers are idempotent: processing an event with a previously-seen `content_hash` is a no-op.

### 6.9 ML Package (`app/ml/`)

- In-process inference only (no model server).
- `classifier.py`: DeBERTa-v3-base ONNX int8 inference via `onnxruntime`.
- `embedder.py`: bge-base-en-v1.5 sentence embeddings via `sentence-transformers`.
- `reranker.py`: ms-marco-MiniLM-L6-v2 cross-encoder reranking.
- `deduplicator.py`: MinHash LSH (datasketch) + pgvector cosine ANN.

### 6.10 Training Codebase (`ml/`)

- Standalone Python package (separate from the serving app).
- `ml/training/`: fine-tuning scripts (HuggingFace Trainer).
- `ml/eval/`: evaluation scripts and metric computation.
- `ml/weak_supervision/`: Snorkel labelling functions.
- `ml/annotation/`: annotation schema + export utilities.

---

## 7. Data Model (conceptual)

### Week 1 — ingestion skeleton

```
sources
├── id              UUID PK (server-generated)
├── name            VARCHAR(128) UNIQUE NOT NULL
├── kind            VARCHAR(64) NOT NULL        -- e.g. "github_issues", "pagerduty", "rss"
├── uri             TEXT NULL                   -- feed / repo URL
├── active          BOOLEAN NOT NULL DEFAULT TRUE
├── created_at      TIMESTAMPTZ (server default)
└── updated_at      TIMESTAMPTZ (server default + on update)

documents
├── id              UUID PK (server-generated)
├── source_id       UUID FK → sources.id ON DELETE CASCADE
├── content_hash    VARCHAR(64) UNIQUE NOT NULL  -- SHA-256, idempotency key
├── title           TEXT NULL
├── body            TEXT NULL
├── doc_metadata    JSONB NOT NULL DEFAULT '{}'
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ

ingest_jobs
├── id              UUID PK (server-generated)
├── source_id       UUID FK → sources.id ON DELETE CASCADE
├── status          VARCHAR(16) NOT NULL DEFAULT 'pending'  -- pending|running|succeeded|failed
├── attempts        SMALLINT NOT NULL DEFAULT 0
├── error           TEXT NULL
├── started_at      TIMESTAMPTZ NULL
├── finished_at     TIMESTAMPTZ NULL
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ
```

### Week 2+ — ML enrichment (added as columns to documents)

```
documents (additional columns — added via migration in Week 2+)
├── severity        SMALLINT NULL               -- 0 (SEV-4) to 4 (SEV-0)
├── incident_type   VARCHAR(64) NULL            -- classifier output label
├── embedding       VECTOR(768) NULL            -- pgvector; bge-base-en-v1.5
└── processed_at    TIMESTAMPTZ NULL

duplicate_pairs (new table — Week 2+)
├── document_a_id   UUID FK → documents.id
├── document_b_id   UUID FK → documents.id
├── similarity      FLOAT4
└── method          VARCHAR(32)                 -- "minhash" | "cosine_ann"
```

---

## 8. API Design Principles

- All endpoints `async`.
- Pagination via `limit`/`offset` query params; default `limit=50`, max `limit=200`.
- Errors return `{"detail": "<message>"}` (FastAPI default).
- `201 Created` for new resources; `202 Accepted` for enqueue-and-return.
- No N+1 queries: repositories use `selectinload` / `joinedload` deliberately.
- Content negotiation: JSON only for v1.

---

## 9. Event Bus Design

Each pipeline step publishes to a dedicated stream:

```
hindsight:ingest.requested  -- ingestion of a source requested
hindsight:doc.fetched       -- document body fetched and stored
hindsight:classify          -- ready for classification (Week 2+)
hindsight:embed             -- ready for embedding (Week 2+)
hindsight:deduplicate       -- ready for deduplication (Week 2+)
hindsight:complete          -- pipeline finished (Week 2+)
```

Failed messages are moved to `<stream>.dlq` (e.g. `hindsight:ingest.requested.dlq`) after retries are exhausted.

Consumer groups:

| Stream | Consumer group | Worker class | Status |
|--------|---------------|-------------|--------|
| `hindsight:ingest.requested` | `echo-cg` | `EchoWorker` | Week 1 (toy, proves chassis) |
| `hindsight:classify` | `classifier-cg` | `ClassifierWorker` | Week 2+ |
| `hindsight:embed` | `embedder-cg` | `EmbedderWorker` | Week 2+ |
| `hindsight:deduplicate` | `deduplicator-cg` | `DeduplicatorWorker` | Week 2+ |

Each message carries `source_id`, `content_hash` (when available), and event metadata. Workers ACK only after a successful DB write. Redelivery on crash is automatic (Redis XAUTOCLAIM with 5-minute idle threshold).

---

## 10. ML Pipeline

```
raw text
  → normalize (lowercase, strip HTML, collapse whitespace)
  → content_hash (SHA-256)          ← idempotency gate
  → DeBERTa-v3-base ONNX int8       → severity + type labels (p99 < 80 ms)
  → bge-base-en-v1.5 embeddings     → 768-dim vector stored in pgvector
  → MinHash LSH (128 permutations)   → candidate duplicate pairs
  → pgvector ANN (ivfflat, lists=100)→ top-k cosine neighbours
  → ms-marco-MiniLM-L6-v2 reranker  → final ranked similar incidents
```

Model files live under `models/` (gitignored). Downloaded/exported at container build time via `scripts/download_models.py` (Week 2).

---

## 11. Authentication & Authorization

- JWT bearer tokens (HS256). Secret from `JWT_SECRET` env var.
- Single role in v1.0: authenticated user can read/write everything.
- RBAC deferred to v2.
- `/api/v1/health` and `/api/v1/docs` are unauthenticated.

---

## 12. Configuration Management

Single source of truth: `app/core/settings.py` — a `pydantic-settings` `BaseSettings` subclass.

All fields map 1:1 to env vars listed in `.env.example`. No config file parsing. No YAML. Tests override config by passing explicit `Settings(...)` instances to service factories.

---

## 13. Testing Strategy

| Layer | Tool | Scope |
|-------|------|-------|
| Unit | pytest + pytest-asyncio | Pure functions, services with fake repos |
| Integration | pytest + testcontainers | Real Postgres + Redis in Docker |
| E2E | pytest + httpx AsyncClient | Full stack against test containers |

Rules:
- Tests bind **fakes** (in-memory repo implementations), never `monkeypatch`.
- Every module ships with at least one unit test.
- Integration tests are tagged `@pytest.mark.integration`; CI runs them in a separate step.
- Coverage target: 80% line coverage enforced in CI from Week 2 onward.

---

## 14. Dependency Injection

FastAPI `Depends` is the only DI mechanism. Pattern:

```python
# app/core/dependencies.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

def get_incident_service(db: AsyncSession = Depends(get_db)) -> IncidentService:
    repo = IncidentRepository(db)
    return IncidentService(repo)
```

Tests pass a `FakeIncidentRepository` directly to `IncidentService(...)` — no patching.

---

## 15. Error Handling & Idempotency

- Every pipeline worker checks `content_hash` in the DB before processing. If present, the worker ACKs the message and returns without side effects.
- DB operations wrapped in explicit transactions; exceptions roll back automatically.
- `409 Conflict` returned by the ingest endpoint if `content_hash` already exists — callers must handle this.

---

## 16. Frontend

- React 18 + TypeScript + Tailwind CSS + shadcn/ui.
- `frontend/` directory is a placeholder in Week 0. Full scaffold in Week 4.
- Served as static files by FastAPI in production (`app.mount("/", StaticFiles(...))`).
- v1.0 is **read-only**: search, browse, filter — no write operations from the UI.

---

## 17. Deployment Topology (target)

```
Single VM / container host (v1.0)
├── hindsight-api        (uvicorn, 2 workers)
├── hindsight-classifier (worker process)
├── hindsight-embedder   (worker process)
├── hindsight-deduplicator (worker process)
├── postgres:16-alpine   (with pgvector extension)
└── redis:7-alpine
```

docker-compose.yml added in Week 1.

---

## 18. Repository Layout

```
hindsight/
├── app/                        # Serving application (Python package)
│   ├── api/
│   │   └── v1/                 # Versioned routers
│   ├── core/                   # Settings, security, lifespan, DI factories
│   ├── events/                 # Redis Streams pub/sub helpers
│   ├── ml/                     # In-process inference modules
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # Data access layer
│   ├── schemas/                # Pydantic request/response models
│   ├── services/               # Business logic orchestration
│   └── workers/                # Async consumer workers
├── ml/                         # Offline training codebase (Python package)
│   ├── annotation/             # Annotation schema and export
│   ├── eval/                   # Evaluation scripts
│   ├── training/               # Fine-tuning scripts
│   └── weak_supervision/       # Snorkel labelling functions
├── tests/
│   ├── unit/                   # Fast, no I/O
│   ├── integration/            # testcontainers (Postgres + Redis)
│   └── e2e/                    # Full-stack httpx tests
├── alembic/                    # Database migrations (Week 1)
│   └── versions/
├── docker/                     # Dockerfiles (Week 1)
├── scripts/                    # Operational scripts
├── frontend/                   # React SPA placeholder (Week 4)
├── docs/
│   ├── SAD.md                  # This document
│   ├── PROGRESS.md             # Weekly progress log
│   └── adr/                   # Architecture Decision Records
├── data/raw/                   # Gitignored raw corpus files
├── .github/workflows/          # CI/CD
├── pyproject.toml              # Project metadata + tool config (uv)
├── .pre-commit-config.yaml
├── .env.example
├── CLAUDE.md                   # AI assistant context
├── CONTRIBUTING.md
└── README.md
```

---

## 19. Architecture Decision Records

ADR files live in `docs/adr/`. Summary of key decisions:

### ADR-0001: PostgreSQL for everything (accepted)

Use PostgreSQL 16 + pgvector as the single data store (relational + vector). Alternatives considered: separate Qdrant/Weaviate vector DB, MongoDB for document storage. Rejected because: single connection pool, ACID transactions across relational and vector data, no additional ops surface. See [docs/adr/0001-postgres-for-everything.md](adr/0001-postgres-for-everything.md).

### ADR-0002: Redis Streams over Kafka (accepted)

Use Redis 7 Streams for the event bus instead of Kafka. Alternatives considered: Kafka, RabbitMQ, in-process asyncio queues. Rejected because: Kafka requires Zookeeper/KRaft and is operationally heavy for v1 throughput (<1k events/day). Redis is already required for caching; Streams add consumer-group semantics at zero additional infrastructure cost. See [docs/adr/0002-redis-streams-over-kafka.md](adr/0002-redis-streams-over-kafka.md).

### ADR-0003: Descope list (accepted)

Items deliberately excluded from v1.0 to keep scope tractable. Listed in §3 Non-Goals.

---

## 20. Glossary

| Term | Definition |
|------|-----------|
| `content_hash` | SHA-256 of normalized incident text; used as idempotency key throughout the pipeline |
| Consumer group | Redis Streams primitive allowing multiple workers to share a stream with at-least-once delivery |
| ONNX int8 | ONNX model with 8-bit integer quantization; reduces model size ~4× with <1% accuracy loss |
| pgvector | PostgreSQL extension for storing and querying dense vectors with L2/cosine/IP distance |
| Fake repository | Test double implementing the repository interface with in-memory storage; not a mock |
| ANN | Approximate Nearest Neighbour search (pgvector ivfflat index) |
| MinHash LSH | Locality-sensitive hashing for near-duplicate detection; fast candidate generation before ANN refinement |
| SEV-0..4 | Severity scale: SEV-0 = total outage, SEV-4 = minor/informational |
