---
language:
  - en
license: apache-2.0
task_categories:
  - text-classification
  - feature-extraction
tags:
  - incidents
  - postmortems
  - site-reliability
  - nlp
  - incident-intelligence
pretty_name: Hindsight Incident Corpus
size_categories:
  - 1K<n<10K
---

# hindsight-corpus

A cleaned, license-audited corpus of public incident postmortems for incident intelligence research.

## Dataset Description

**hindsight-corpus** contains structured records of publicly available incident postmortems collected from curated link collections. Each record includes metadata (organization, title, URL, date, severity estimate) and section annotations. Full text is included only for records with permissive licenses.

### Source Collections
- [danluu/post-mortems](https://github.com/danluu/post-mortems) — curated list of postmortem links
- [hjacobs/kubernetes-failure-stories](https://github.com/hjacobs/kubernetes-failure-stories) — Kubernetes-specific incident reports

## Dataset Structure

### Features

| Feature | Type | Description |
|---------|------|-------------|
| `id` | `string` | UUID identifier for the incident |
| `org` | `string` | Organization (extracted from URL domain) |
| `title` | `string` | Incident title |
| `url` | `string` | Source URL |
| `date` | `string` | ISO 8601 date (empty if unknown) |
| `severity` | `int32` | Heuristic severity: 0 (critical) to 3 (minor), -1 (unknown) |
| `sections` | `string` | JSON array of detected section types |
| `license` | `string` | Detected license (SPDX-like identifier) |
| `full_text` | `string` | Summary text (empty for non-permissive records) |
| `content_hash` | `string` | SHA-256 of normalized text |

### Splits

| Split | Records | Description |
|-------|---------|-------------|
| `train` | >=1,500 | All deduplicated, English-language incidents |

### Section Types Detected
- `impact` / `blast radius`
- `timeline` / `chronology`
- `root cause` / `cause`
- `lessons learned` / `takeaways` / `action items`
- `mitigation` / `remediation` / `resolution` / `recovery`
- `detection` / `monitoring` / `alerting`
- `prevention` / `follow-up`
- `summary` / `overview` / `abstract` / `background`

### Severity Scale

| Value | Label | Description |
|-------|-------|-------------|
| 0 | SEV-0 | Total outage, data loss, data breach |
| 1 | SEV-1 | Major outage, significant impact |
| 2 | SEV-2 | Partial outage, degraded service |
| 3 | SEV-3 | Minor issue, intermittent disruption |
| -1 | Unknown | No severity keywords detected |

## Usage

```python
from datasets import load_dataset

ds = load_dataset("RahuL0009/hindsight-corpus")
print(ds["train"][0])
```

## License Policy

The dataset tooling and metadata schema are licensed under **Apache-2.0**.

Individual incident records retain their original licenses, detected per-record:
- Records with permissive licenses (CC-BY, MIT, Apache-2.0, etc.) include `full_text`.
- Records with `all-rights-reserved` include metadata only — `full_text` is empty.

This ensures zero records ship full text without a permissive license flag.

## Processing Pipeline

1. **Seed loading** — Extract URLs from curated markdown collections
2. **Crawling** — HTTP fetch with SSRF protection, robots.txt compliance, politeness (2s/domain)
3. **Parsing** — HTML-to-text (trafilatura + readability-lxml), NFC normalization, language filter
4. **Deduplication** — MinHash LSH (128 perms, band-size 4, Jaccard > 0.85)
5. **Promotion** — Metadata extraction (org, date, severity, sections)
6. **License audit** — Per-record license detection from text patterns
7. **Export** — Deterministic ordering (by content_hash), SHA-256 manifest

## Reproducibility

Re-running the export pipeline against the same database state produces a byte-identical dataset. The export includes a `manifest.json` with:
- Dataset version (git tag)
- Record count
- SHA-256 hash of all Parquet files

## Citation

```bibtex
@dataset{hindsight_corpus_2026,
  title={Hindsight Incident Corpus},
  author={Hindsight Contributors},
  year={2026},
  url={https://github.com/RahulMishra09/Hindsight},
  version={0.1.0}
}
```

## Datasheet

See [docs/datasheet.md](https://github.com/RahulMishra09/Hindsight/blob/main/docs/datasheet.md) for the full datasheet following Gebru et al. (2021).
