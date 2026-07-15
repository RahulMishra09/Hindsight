# Datasheet: hindsight-corpus v0.1

_Following the template from Gebru et al., "Datasheets for Datasets" (2021)._

---

## Motivation

**For what purpose was the dataset created?**
To provide a structured, license-audited corpus of public incident postmortems for research in incident intelligence, NLP classification, severity estimation, and semantic search.

**Who created the dataset and on behalf of which entity?**
Created by the Hindsight project contributors as part of an open-source incident-intelligence platform.

**Who funded the creation of the dataset?**
No external funding. Created as an open-source research project.

---

## Composition

**What do the instances represent?**
Each instance represents a single, deduplicated incident postmortem report. An incident is a public document describing a software/infrastructure failure, its impact, root cause, timeline, and remediation steps.

**How many instances are there in total?**
v0.1 targets >=1,500 records sourced from curated postmortem link collections.

**Does the dataset contain all possible instances or is it a sample?**
It is a sample. The dataset is derived from two curated link collections (danluu/post-mortems and hjacobs/kubernetes-failure-stories) and includes only documents that were publicly accessible at crawl time, parseable, English-language, and non-duplicate.

**What data does each instance consist of?**
| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Unique incident identifier |
| org | string | Organization extracted from URL domain |
| title | string | Incident title (from HTML or metadata) |
| url | string | Source URL of the postmortem |
| date | string (ISO 8601) | Estimated incident date (may be empty) |
| severity | int32 | Heuristic severity (0=SEV-0 critical, 3=SEV-3 minor, -1=unknown) |
| sections | string (JSON array) | Detected section types (e.g., root cause, timeline, impact) |
| license | string | Detected license identifier (SPDX-like) |
| full_text | string | Summary text (only populated for permissive-licensed records) |
| content_hash | string | SHA-256 hash of normalized text (idempotency key) |

**Is there a label or target associated with each instance?**
No. Labels (incident type, fine-grained severity) are planned for v0.2+ (Weeks 4-5).

**Is any information missing from individual instances?**
- `date` may be empty if no date could be parsed from the title or body.
- `severity` is -1 when no severity keywords were detected.
- `full_text` is empty for records without a permissive license.

**Are there any errors, sources of noise, or redundancies?**
- Org extraction is heuristic (URL domain parsing) and may be inaccurate for CDN-hosted or aggregator pages.
- Severity estimation uses keyword matching, not ML classification; accuracy is limited.
- Date extraction may pick up unrelated dates from document body.
- Near-duplicate detection (MinHash LSH, Jaccard > 0.85) may miss some duplicates or flag near-matches incorrectly.

**Is the dataset self-contained?**
Yes. The dataset is fully self-contained and does not require access to external resources. Source URLs are included for provenance but are not required for use.

---

## Collection Process

**How was the data associated with each instance acquired?**
Instances were collected through a multi-stage automated pipeline:
1. **Seed loading**: URLs extracted from curated markdown link collections (danluu/post-mortems, hjacobs/kubernetes-failure-stories).
2. **Crawling**: HTTP GET with SSRF protection, robots.txt compliance, and per-domain politeness (2s delay).
3. **Parsing**: HTML-to-text extraction via trafilatura with readability-lxml fallback, NFC normalization, ASCII-ratio language filtering.
4. **Deduplication**: MinHash LSH (128 permutations, band-size 4, Jaccard > 0.85 threshold).
5. **Promotion**: Deduplicated documents promoted to incident records with heuristic metadata extraction.
6. **License audit**: Per-record license detection from text patterns and source metadata.

**What mechanisms or procedures were used to collect the data?**
Fully automated pipeline. No manual annotation or curation was performed on individual records.

**If the dataset relates to people, are there any ethical considerations?**
The dataset contains publicly posted incident reports about software systems, not personal data. Some reports may mention individuals by name or role in the context of incident response. No PII scrubbing was applied because the source documents are public postmortems intended for broad distribution.

**Over what timeframe was the data collected?**
Source documents span from approximately 2012 to 2026, based on publication dates. The crawl was performed in July 2026.

---

## Preprocessing / Cleaning / Labeling

**Was any preprocessing/cleaning/labeling of the data done?**
- HTML stripped via trafilatura + readability-lxml
- Unicode NFC normalization applied
- Non-English documents filtered (ASCII ratio < 0.8)
- Near-duplicates removed via MinHash LSH
- No manual labeling performed in v0.1

**Was the "raw" data saved in addition to the preprocessed/cleaned/labeled data?**
Yes. The raw HTML is stored in the documents table (status=FETCHED) but is not included in the exported dataset.

---

## Uses

**What tasks has the dataset been used for?**
The dataset is designed for:
- Incident classification (type and severity)
- Semantic search over postmortems
- Pattern detection across incident reports
- Training and evaluation of incident-intelligence NLP models

**Is there anything about the composition of the dataset or the way it was collected that might impact future uses?**
- English-only: non-English postmortems are excluded.
- Source bias: limited to links curated in two specific collections; does not represent all public postmortems.
- Temporal bias: overrepresents incidents from organizations that publish postmortems publicly.

**Are there tasks for which the dataset should not be used?**
This dataset should not be used to evaluate individual engineers or organizations, attribute blame for incidents, or make employment decisions.

---

## Distribution

**How will the dataset be distributed?**
Published on HuggingFace Hub as a Parquet-backed dataset under the repository `RahuL0009/hindsight-corpus`.

**When will the dataset be distributed?**
v0.1 released July 2026.

**Will the dataset be distributed under a copyright or other intellectual property (IP) license?**
The dataset metadata and tooling are licensed under Apache-2.0. Individual incident records retain their original licenses (detected per-record). Full text is only distributed for records with permissive licenses. Records with "all-rights-reserved" include metadata only (no full text).

---

## Maintenance

**Who is supporting/hosting/maintaining the dataset?**
The Hindsight project maintainers.

**How can the owner/curator/manager of the dataset be contacted?**
Via the GitHub repository: https://github.com/RahulMishra09/Hindsight

**Will the dataset be updated?**
Yes. The dataset will be versioned and updated as the pipeline ingests new sources and adds ML-derived labels (planned for v0.2+).

**Will older versions of the dataset continue to be supported/hosted/maintained?**
Yes. Each version is tagged and can be loaded from HuggingFace Hub by version.

**If others want to extend/augment/build on/contribute to the dataset, is there a mechanism for them to do so?**
Contributions are welcome via the GitHub repository. New postmortem sources can be added to the seed loader, and the full pipeline will process them through crawl, parse, dedup, and export stages.
