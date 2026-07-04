# ADR-0001: PostgreSQL for Everything

**Date:** 2026-07-04
**Status:** Accepted
**Deciders:** Core team

---

## Context

Hindsight needs to store:

1. Structured incident records (relational data with strict schema).
2. Dense vector embeddings (768-dim bge-base-en-v1.5 outputs) for ANN similarity search.
3. Potentially sparse metadata blobs (JSONB) for source-specific fields.

We need to decide whether to use a single data store or split across specialized systems.

### Options Considered

**Option A: PostgreSQL 16 + pgvector (single store)**
Use PostgreSQL for all three data types. Enable the `pgvector` extension for vector column storage and ANN indexing (ivfflat).

**Option B: PostgreSQL (relational) + Qdrant (vectors)**
Keep relational data in PostgreSQL and offload vector storage to a dedicated Qdrant instance.

**Option C: PostgreSQL (relational) + Weaviate (vectors + semantic)**
Same split, but use Weaviate which embeds an ML runtime.

**Option D: MongoDB (documents + BSON) + Pinecone (vectors)**
Document-oriented storage for incidents; managed vector DB for embeddings.

---

## Decision

**Option A: PostgreSQL 16 + pgvector.**

---

## Rationale

1. **Single connection pool.** One database means one `asyncpg` pool, one set of credentials, one backup target, one recovery procedure. Options B–D require maintaining two or more connection pools and handling split-brain scenarios.

2. **ACID across relational and vector data.** When a classifier writes a severity score and an embedder writes a vector for the same incident, both writes can be wrapped in a single transaction. With a split architecture, this coordination requires distributed transactions or application-level sagas — significant complexity for v1.

3. **No additional ops surface.** Qdrant, Weaviate, and Pinecone each add a service to deploy, monitor, scale, and back up. For v1 (single node, < 100k incidents), this overhead is unjustified.

4. **pgvector ivfflat is sufficient for v1 scale.** At < 100k vectors (768-dim), ivfflat with `lists=100` delivers sub-10ms ANN queries. Dedicated vector DBs provide marginal performance gains that do not materialize at this scale.

5. **JSONB for metadata.** PostgreSQL's JSONB type covers the schema-flexible metadata requirement without a document database.

6. **Ecosystem maturity.** SQLAlchemy 2 + asyncpg + pgvector have production-grade Python support. Integrating Qdrant or Weaviate would require maintaining additional async client libraries.

### Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| pgvector ANN accuracy/speed degrades beyond 1M vectors | ivfflat → hnsw index upgrade path exists in pgvector; or migrate to dedicated vector DB at that scale |
| PostgreSQL becomes a write bottleneck under high ingestion | Add read replica (explicitly descoped for v1; see SAD §3 Non-Goals) |
| pgvector extension not available in managed Postgres offerings | Document requirement in CONTRIBUTING.md and deployment guide |

---

## Consequences

- `app/models/` contains SQLAlchemy mapped classes with `Vector(768)` columns.
- `alembic/` manages schema migrations including vector index creation.
- No Qdrant, Weaviate, Pinecone, or Milvus client is ever imported.
- Tests use `testcontainers` to spin up a real `postgres:16-alpine` with pgvector; no SQLite.
