# Hindsight

[![CI](https://github.com/RahulMishra09/Hindsight/actions/workflows/ci.yml/badge.svg)](https://github.com/RahulMishra09/Hindsight/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Dataset](https://img.shields.io/badge/🤗%20Dataset-hindsight--corpus-yellow.svg)](https://huggingface.co/datasets/RahuL0009/hindsight-corpus)
[![Model](https://img.shields.io/badge/🤗%20Model-hindsight--taxonomy-yellow.svg)](https://huggingface.co/RahuL0009/hindsight-taxonomy)

**Open incident-intelligence platform.** Hindsight ingests raw incident post-mortems, applies NLP enrichment (multi-label taxonomy classification, severity estimation, near-duplicate detection), and surfaces actionable patterns through a versioned REST API — entirely self-hostable, reproducible, and open-source.

> See [docs/SAD.md](docs/SAD.md) for the full architecture and [docs/PROGRESS.md](docs/PROGRESS.md) for weekly progress.

---

## Pipeline

```
Sources (danluu, k8s-failures, …)
  │
  ▼
CrawlerWorker ─── fetch HTML, SSRF guard, robots.txt, politeness
  │
  ▼
ParserWorker ──── extract text, NFC normalize, detect sections
  │
  ▼
DeduperWorker ─── MinHash LSH near-duplicate detection
  │
  ▼
Promoter ──────── extract org, severity, date → Incident row
  │
  ▼
ClassifierWorker ─ DeBERTa-v3 per-section inference → 15 taxonomy labels
  │
  ▼
doc.classified ── ready for search, analysis, export
```

---

## Taxonomy (15 labels)

| Label | Description |
|-------|-------------|
| config-change | Misconfiguration or feature flag change |
| retry-storm | Cascading retries amplifying load |
| cascading-failure | Failure propagating across services |
| dns | DNS resolution or routing issue |
| certificate-expiry | TLS/SSL certificate expiry |
| capacity-exhaustion | OOM, disk full, resource exhaustion |
| bad-deploy | Faulty deployment or rollback |
| dependency-failure | Third-party or cloud provider failure |
| network-partition | Network split, firewall, connectivity |
| database-failure | DB deadlock, replication lag |
| thundering-herd | Cache stampede or thundering herd |
| monitoring-gap | Missing or delayed alerting |
| human-error | Manual mistake or wrong environment |
| data-corruption | Data integrity or race condition |
| quota-limit | Rate limiting or quota breach |

See [docs/taxonomy.md](docs/taxonomy.md) for full definitions with inclusion/exclusion criteria and examples.

---

## Artefacts

| Artefact | Description | Location |
|----------|-------------|----------|
| **Labelled Dataset** | Curated incident corpus with severity + type labels | [Hugging Face Hub](https://huggingface.co/datasets/RahuL0009/hindsight-corpus) |
| **Classification Model** | DeBERTa-v3-base multi-label, ONNX int8 quantized | [Hugging Face Hub](https://huggingface.co/RahuL0009/hindsight-taxonomy) |
| **System** | Self-hostable Docker Compose stack with API + workers | This repository |

---

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 async · PostgreSQL 16 + pgvector · Redis 7 Streams · DeBERTa-v3-base ONNX · React + TypeScript + Tailwind

---

## Quick Start

```bash
# Clone
git clone https://github.com/RahulMishra09/Hindsight.git
cd Hindsight

# Install dependencies
uv sync

# Copy env template
cp .env.example .env

# Start services
docker compose up -d

# Run migrations
uv run alembic upgrade head

# Seed the pipeline (fetches incident URLs from curated lists)
uv run python -m app.ingest

# Start a worker (crawler | parser | deduper | classifier)
uv run python -m app.workers crawler
```

### Training the classifier

```bash
# Run weak supervision to generate silver labels
uv run python scripts/reconcile_labels.py

# Train DeBERTa-v3-base
uv run python -m ml.training.run --config ml/training/config.yaml

# Export to ONNX int8
uv run python -m ml.export.onnx_export \
  --model models/deberta-taxonomy/best \
  --out models/deberta-taxonomy/onnx

# Backfill classification on all incidents
uv run python scripts/backfill_classify.py \
  --model models/deberta-taxonomy/best
```

---

## Development

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy .

# Run tests (342 unit tests)
uv run pytest

# Pre-commit on all files
pre-commit run --all-files
```

---

## Documentation

- [System Architecture Document](docs/SAD.md) — full design, data model, API principles, ML pipeline
- [Progress Log](docs/PROGRESS.md) — weekly shipped/cut/risks
- [Taxonomy](docs/taxonomy.md) — 15-label incident root-cause taxonomy
- [Datasheet](docs/datasheet.md) — dataset documentation (Gebru et al.)
- [Dataset Card](docs/dataset_card.md) — HF Hub dataset card
- [ADR-0001: PostgreSQL for everything](docs/adr/0001-postgres-for-everything.md)
- [ADR-0002: Redis Streams over Kafka](docs/adr/0002-redis-streams-over-kafka.md)
- [Contributing Guide](CONTRIBUTING.md)

---

## Project Status

**Current week:** Week 5 (complete) — DeBERTa classifier training, evaluation, ONNX export, ClassifierWorker.

**Next milestone:** Week 6 — embeddings (bge-base-en-v1.5), semantic search, retrieval API.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
