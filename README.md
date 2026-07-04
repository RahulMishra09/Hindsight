# Hindsight

[![CI](https://github.com/rahulmishra/hindsight/actions/workflows/ci.yml/badge.svg)](https://github.com/rahulmishra/hindsight/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Dataset](https://img.shields.io/badge/🤗%20Dataset-coming%20Week%203-orange.svg)](#)
[![Model](https://img.shields.io/badge/🤗%20Model-coming%20Week%205-orange.svg)](#)

**Open incident-intelligence platform.** Hindsight ingests raw incident post-mortems, applies NLP enrichment (classification, severity estimation, near-duplicate detection, semantic similarity), and surfaces actionable patterns through a versioned REST API and a lightweight React dashboard — entirely self-hostable, reproducible, and open-source.

> **Status: Under Construction** — repository bootstrapped, application coming in Week 1.
> See [docs/SAD.md](docs/SAD.md) for the full architecture and [docs/PROGRESS.md](docs/PROGRESS.md) for current status.

---

## Planned Artefacts

| Artefact | Description | Release |
|----------|-------------|---------|
| **Labelled Dataset** | Curated incident corpus with severity + type labels | Hugging Face Hub, Week 3 |
| **Classification Model** | DeBERTa-v3-base fine-tuned on incident data, ONNX int8 | Hugging Face Hub, Week 5 |
| **System** | Self-hostable Docker Compose stack with API + workers + dashboard | GitHub Releases, Week 6 |

---

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 async · PostgreSQL 16 + pgvector · Redis 7 Streams · DeBERTa-v3-base ONNX · React + TypeScript + Tailwind

---

## Quick Start (coming Week 1)

```bash
# Clone
git clone https://github.com/rahulmishra/hindsight.git
cd hindsight

# Install dependencies
uv sync

# Copy env template
cp .env.example .env

# Start services (Week 1)
# docker compose up -d
```

---

## Documentation

- [System Architecture Document](docs/SAD.md) — full design, data model, API principles, ML pipeline
- [Progress Log](docs/PROGRESS.md) — weekly shipped/cut/risks
- [ADR-0001: PostgreSQL for everything](docs/adr/0001-postgres-for-everything.md)
- [ADR-0002: Redis Streams over Kafka](docs/adr/0002-redis-streams-over-kafka.md)
- [Contributing Guide](CONTRIBUTING.md)

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
