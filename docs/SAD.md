# Hindsight — System Architecture Document

**Version:** 0.5.0
**Date:** 2026-07-20
**Status:** Living document — updated each sprint

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [System Context](#4-system-context)
5. [High-Level Architecture](#5-high-level-architecture)
6. [Component Breakdown](#6-component-breakdown)
7. [Data Model](#7-data-model)
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

Hindsight is an **open incident-intelligence platform** that ingests raw incident reports, applies NLP enrichment (multi-label taxonomy classification, severity estimation, near-duplicate detection, semantic search), and surfaces actionable patterns through a REST API and a lightweight React dashboard.

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
- Classify incident type via 15-label taxonomy with a fine-tuned DeBERTa-v3-base model (ONNX int8 for CPU inference).
- Detect near-duplicates via MinHash LSH.
- Embed incidents via bge-base-en-v1.5 for semantic search (Week 6).
- Rank semantically similar incidents via ms-marco-MiniLM-L6-v2 cross-encoder (Week 6).
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
              ┌──────────────┬─────────────────┼────────────────┬──────────────┐
              │              │                 │                │              │
   ┌──────────▼───┐ ┌────────▼─────┐ ┌────────▼─────┐ ┌───────▼──────┐ ┌─────▼────────┐
   │  Crawler     │ │  Parser      │ │  Deduper     │ │  Classifier  │ │  Embedder    │
   │  Worker      │ │  Worker      │ │  Worker      │ │  Worker      │ │  Worker      │
   │ (httpx+SSRF) │ │(trafilatura) │ │ (MinHash LSH)│ │(DeBERTa ONNX)│ │(bge-base,Wk6)│
   └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
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
- `db.py`: `create_engine()`, `create_sessionmaker()`, `create_redis()` factory functions.
- `logging.py`: structlog-based structured logging configuration.

### 6.3 Models (`app/models/`)

- SQLAlchemy 2 declarative mapped classes only.
- No business logic. No classmethods that touch the DB directly.
- `Base` defined in `base.py` with `UUIDPrimaryKeyMixin` and `TimestampMixin`; imported by `alembic/env.py`.
- Tables: `sources`, `documents`, `ingest_jobs`, `incidents`, `incident_labels`, `minhash_signatures`.

### 6.4 Schemas (`app/schemas/`)

- Pydantic v2 request/response models.
- `health.py`: health check response.
- `ingest.py`: source and ingestion request/response models.

### 6.5 Repositories (`app/repositories/`)

- **The only layer that imports SQLAlchemy.**
- One repository class per aggregate root.
- Methods are `async` and accept an `AsyncSession` injected via constructor.
- Repositories: `DocumentRepository`, `SourceRepository`, `IncidentRepository`, `IncidentLabelRepository`, `MinHashRepository`, `HealthRepository`.

### 6.6 Services (`app/services/`)

- Orchestration layer: calls repositories, emits Redis events, applies business rules.
- `health.py`: health check (DB + Redis liveness).
- `ingest.py`: source/job management and pipeline seeding.
- `promoter.py`: extracts structured incident metadata (org, severity, date) from parsed documents and creates `Incident` rows.
- `license_audit.py`: validates license compatibility before dataset export.
- Tests use fake repositories injected at the factory level — never `monkeypatch`.

### 6.7 Events (`app/events/`)

- Redis Streams publish/consume helpers.
- `publisher.py`: thin async wrapper around `redis.asyncio` XADD.
- `consumer.py`: `BaseWorker[TEvent]` generic base class with XREADGROUP + ACK loop, DLQ routing, and graceful shutdown.
- `schemas.py`: typed event models (`IngestRequested`, `DocDiscovered`, `DocFetched`, `DocParsed`, `DocDeduped`, `DocClassified`).
- `streams.py`: canonical stream names and consumer group constants.
- Each worker registers **one consumer group**; multiple instances of the same worker share the group.

### 6.8 Workers (`app/workers/`)

- Long-running async consumer processes (not threads, not Celery tasks).
- Each worker subclasses `BaseWorker[TEvent]` and implements `handle(event)`.
- Workers are idempotent: processing an event with a previously-seen `content_hash` is a no-op.
- Worker types: `CrawlerWorker`, `ParserWorker`, `DeduperWorker`, `ClassifierWorker`, `EchoWorker` (toy).
- `__main__.py` dispatches `python -m app.workers <type>`.

### 6.9 Ingest Package (`app/ingest/`)

- `seed_loader.py`: loads curated incident URLs from seed files into the pipeline.
- `ssrf_guard.py`: validates URLs against SSRF (blocks private IPs, local networks).
- `politeness.py`: per-host rate limiting for crawler.
- `robots.py`: robots.txt parsing and compliance.

### 6.10 ML Inference (`app/ml/`)

- In-process inference only (no model server).
- `classifier.py`: `TaxonomyClassifier` — DeBERTa-v3-base per-section inference with max-pool aggregation across document sections. Loads thresholds from `thresholds.json`. Supports long documents by splitting into sections.

### 6.11 Training Codebase (`ml/`)

- Standalone Python package (separate from the serving app).
- `ml/training/config.py`: `TrainPipelineConfig` (pydantic-settings, env-var overrides with `TRAIN_*` prefix).
- `ml/training/data.py`: data loading, multi-label stratified split (iterative-stratification), pos_weight computation, silver/gold label merging.
- `ml/training/trainer.py`: DeBERTa fine-tuning with HuggingFace Trainer (BCE loss, per-label pos_weight, early stopping).
- `ml/training/threshold.py`: per-label F1 threshold tuning via grid search on validation set.
- `ml/training/run.py`: CLI entry point orchestrating data → train → threshold tune.
- `ml/eval/evaluator.py`: micro/macro-F1, per-label P/R/F1, ECE calibration, slice metrics, baseline save/load, regression gate.
- `ml/eval/golden_set.py`: exports gold-annotated incidents to frozen JSONL for evaluation.
- `ml/eval/run.py`: evaluation entry point loading golden set and running inference.
- `ml/export/onnx_export.py`: ONNX export with int8 dynamic quantization, parity check, latency benchmark.
- `ml/weak_supervision/keyword_lfs.py`: keyword-based labelling functions for 15 taxonomy categories.
- `ml/weak_supervision/llm_lf.py`: LLM-based labelling function via Groq API.
- `ml/weak_supervision/voter.py`: majority-vote label reconciliation across LF outputs.

---

## 7. Data Model

### Core Tables

```
sources
├── id              UUID PK
├── name            VARCHAR(128) UNIQUE NOT NULL
├── kind            VARCHAR(64) NOT NULL
├── uri             TEXT NULL
├── active          BOOLEAN NOT NULL DEFAULT TRUE
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ

documents
├── id              UUID PK
├── source_id       UUID FK → sources.id ON DELETE CASCADE
├── content_hash    VARCHAR(64) NOT NULL (unique per source)
├── title           TEXT NULL
├── body            TEXT NULL
├── url             TEXT NULL
├── status          VARCHAR(16) NOT NULL DEFAULT 'pending'
│                   (pending|fetched|parsed|promoted|failed)
├── failed_stage    VARCHAR(32) NULL
├── doc_metadata    JSONB NOT NULL DEFAULT '{}'
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ

ingest_jobs
├── id              UUID PK
├── source_id       UUID FK → sources.id ON DELETE CASCADE
├── status          VARCHAR(16) NOT NULL DEFAULT 'pending'
│                   (pending|running|succeeded|failed)
├── attempts        SMALLINT NOT NULL DEFAULT 0
├── error           TEXT NULL
├── started_at      TIMESTAMPTZ NULL
├── finished_at     TIMESTAMPTZ NULL
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ

incidents
├── id              UUID PK
├── document_id     UUID FK → documents.id UNIQUE
├── org             VARCHAR(256) NOT NULL
├── title           TEXT NOT NULL
├── url             TEXT NULL
├── occurred_on     DATE NULL
├── severity        SMALLINT NULL (0=SEV-4 to 4=SEV-0)
├── summary         TEXT NULL
├── sections        JSONB NOT NULL DEFAULT '{}'
├── content_hash    VARCHAR(64) NOT NULL
├── license         VARCHAR(64) NOT NULL DEFAULT 'unknown'
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ

incident_labels
├── id              UUID PK
├── incident_id     UUID FK → incidents.id ON DELETE CASCADE
├── label           VARCHAR(64) NOT NULL
├── source          VARCHAR(16) NOT NULL (weak|human|model)
├── confidence      FLOAT NULL
├── model_version   VARCHAR(64) NULL
├── annotator_id    VARCHAR(128) NOT NULL DEFAULT 'system'
├── annotation_round SMALLINT NULL
├── created_at      TIMESTAMPTZ
├── updated_at      TIMESTAMPTZ
└── UNIQUE(incident_id, label, annotator_id)

minhash_signatures
├── id              UUID PK
├── document_id     UUID FK → documents.id UNIQUE
├── num_perm        SMALLINT NOT NULL
├── band_hashes     JSONB NOT NULL
├── hashvalues      JSONB NOT NULL
├── band_size       SMALLINT NOT NULL DEFAULT 4
├── canonical_id    VARCHAR(36) NULL
├── created_at      TIMESTAMPTZ
└── updated_at      TIMESTAMPTZ
```

### Migrations (linear chain)

| Migration | Description |
|-----------|-------------|
| `0001_initial_schema` | sources, documents, ingest_jobs |
| `0002_pipeline_columns` | url, status, failed_stage on documents; minhash_signatures |
| `0003_incidents_table` | incidents table |
| `0004_incident_labels` | incident_labels with unique constraint |

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
hindsight:doc.discovered    -- URL discovered by seed loader
hindsight:doc.fetched       -- document body fetched and stored
hindsight:doc.parsed        -- document text extracted and sections detected
hindsight:doc.deduped       -- near-duplicate check completed
hindsight:doc.classified    -- taxonomy labels assigned
```

Failed messages are moved to `<stream>.dlq` (e.g. `hindsight:doc.fetched.dlq`) after retries are exhausted.

Consumer groups:

| Stream | Consumer group | Worker class | Status |
|--------|---------------|-------------|--------|
| `hindsight:ingest.requested` | `echo-cg` | `EchoWorker` | Week 1 (toy, proves chassis) |
| `hindsight:doc.discovered` | `crawler-cg` | `CrawlerWorker` | Week 2 |
| `hindsight:doc.fetched` | `parser-cg` | `ParserWorker` | Week 2 |
| `hindsight:doc.parsed` | `deduper-cg` | `DeduperWorker` | Week 2 |
| `hindsight:doc.deduped` | `classifier-cg` | `ClassifierWorker` | Week 5 |

Each message carries typed event fields (see `app/events/schemas.py`). Workers ACK only after a successful DB write. Redelivery on crash is automatic (Redis XAUTOCLAIM with 5-minute idle threshold).

---

## 10. ML Pipeline

### Inference Pipeline (per incident)

```
raw text
  → CrawlerWorker: fetch HTML, SSRF guard, robots.txt, politeness
  → ParserWorker: trafilatura extraction, NFC normalize, section detection
  → Promoter: extract org, severity, date → Incident row
  → DeduperWorker: MinHash LSH (128 perm, 4 bands) → dedup check
  → ClassifierWorker: split sections → DeBERTa-v3-base → max-pool → 15 labels
  → (Week 6) EmbedderWorker: bge-base-en-v1.5 → 768-dim vector → pgvector
```

### Training Pipeline (offline)

```
1. Weak supervision: keyword LFs + LLM LF → silver labels
2. Human annotation: Streamlit app → gold labels
3. Label reconciliation: majority vote → merged labels
4. Data preparation: multi-label stratified split (iterative-stratification)
5. DeBERTa-v3-base fine-tuning: BCE loss + per-label pos_weight, early stopping
6. Per-label threshold tuning: grid search [0.1, 0.9] maximizing F1
7. Evaluation: micro/macro-F1, per-label P/R/F1, ECE calibration, slice metrics
8. ONNX export: int8 dynamic quantization via optimum
9. Regression gate: baseline.json comparison (macro_f1_drop ≤ 0.01, label_f1_drop ≤ 0.03)
```

### Taxonomy (15 labels)

config-change, retry-storm, cascading-failure, dns, certificate-expiry, capacity-exhaustion, bad-deploy, dependency-failure, network-partition, database-failure, thundering-herd, monitoring-gap, human-error, data-corruption, quota-limit.

See [docs/taxonomy.md](taxonomy.md) for full definitions.

Model files live under `models/` (gitignored). ONNX export via `ml/export/onnx_export.py`.

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

Training hyperparameters: `ml/training/config.py` — `TrainPipelineConfig` (pydantic-settings with `TRAIN_*` env prefix).

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
- Coverage gate: `fail_under = 55` enforced in CI via pytest-cov.

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
- `frontend/` directory is a placeholder. Full scaffold in Week 6+.
- Served as static files by FastAPI in production (`app.mount("/", StaticFiles(...))`).
- v1.0 is **read-only**: search, browse, filter — no write operations from the UI.

---

## 17. Deployment Topology (target)

```
Single VM / container host (v1.0)
├── hindsight-api        (uvicorn, 2 workers)
├── hindsight-crawler    (worker process)
├── hindsight-parser     (worker process)
├── hindsight-deduper    (worker process)
├── hindsight-classifier (worker process)
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
│   ├── core/                   # Settings, security, lifespan, DI, db, logging
│   ├── events/                 # Redis Streams pub/sub + event schemas
│   ├── ingest/                 # Seed loader, SSRF guard, politeness, robots
│   ├── ml/                     # In-process inference (classifier)
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # Data access layer
│   ├── schemas/                # Pydantic request/response models
│   ├── services/               # Business logic orchestration
│   └── workers/                # Async consumer workers
├── ml/                         # Offline training codebase (Python package)
│   ├── annotation/             # Annotation schema and export
│   ├── eval/                   # Evaluation, golden set, regression gate
│   ├── export/                 # ONNX export + quantization
│   ├── training/               # Fine-tuning, data prep, threshold tuning
│   └── weak_supervision/       # Keyword + LLM labelling functions, voter
├── scripts/                    # Operational scripts
│   ├── reconcile_labels.py     # Run weak supervision label reconciliation
│   ├── export_dataset.py       # Export dataset to HF Hub
│   ├── backfill_classify.py    # Batch-classify all unclassified incidents
│   ├── push_model_to_hub.py    # Push ONNX model to HF Hub
│   └── agreement.py            # Inter-annotator agreement metrics
├── tests/
│   ├── unit/                   # Fast, no I/O
│   ├── integration/            # testcontainers (Postgres + Redis)
│   ├── e2e/                    # Full-stack httpx tests
│   └── fixtures/               # Test data (golden set, etc.)
├── alembic/                    # Database migrations
│   └── versions/               # 0001–0004 linear chain
├── docs/
│   ├── SAD.md                  # This document
│   ├── PROGRESS.md             # Weekly progress log
│   ├── taxonomy.md             # 15-label taxonomy definitions
│   ├── datasheet.md            # Dataset documentation (Gebru et al.)
│   ├── dataset_card.md         # HF Hub dataset card
│   └── adr/                    # Architecture Decision Records
├── data/raw/                   # Gitignored raw corpus files
├── data/export/                # Gitignored export files
├── models/                     # Gitignored trained model artefacts
├── .github/workflows/          # CI/CD (ci.yml, publish.yml)
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
| MinHash LSH | Locality-sensitive hashing for near-duplicate detection; fast candidate generation |
| SEV-0..4 | Severity scale: SEV-0 = total outage, SEV-4 = minor/informational |
| Taxonomy | 15-label classification of incident root causes (see docs/taxonomy.md) |
| Silver label | Programmatically generated label from weak supervision (keyword/LLM labelling functions) |
| Gold label | Human-annotated label from annotation interface |
| Regression gate | CI check that prevents model quality from dropping below baseline thresholds |
