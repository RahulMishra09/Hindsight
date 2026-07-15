"""Generate stats tables for the dataset card.

Usage: python -m scripts.dataset_stats --export-dir data/export
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def load_records(export_dir: str) -> list[dict[str, object]]:
    try:
        import datasets

        ds = datasets.load_from_disk(export_dir)
        if isinstance(ds, datasets.DatasetDict):
            ds = ds["train"]
        return [dict(row) for row in ds]
    except Exception:
        return []


def generate_stats(records: list[dict[str, object]]) -> str:
    total = len(records)
    if total == 0:
        return "No records found."

    lines: list[str] = []
    lines.append(f"## Dataset Statistics (n={total})")
    lines.append("")

    sev_counts: Counter[int] = Counter()
    for r in records:
        sev_val = r.get("severity", -1)
        sev_counts[int(str(sev_val))] += 1

    lines.append("### Severity Distribution")
    lines.append("")
    lines.append("| Severity | Count | % |")
    lines.append("|----------|-------|---|")
    for sev in sorted(sev_counts.keys()):
        label = {0: "SEV-0", 1: "SEV-1", 2: "SEV-2", 3: "SEV-3", -1: "Unknown"}.get(sev, str(sev))
        count = sev_counts[sev]
        pct = count / total * 100
        lines.append(f"| {label} | {count} | {pct:.1f}% |")
    lines.append("")

    org_counts: Counter[str] = Counter()
    for r in records:
        org_counts[str(r.get("org", "unknown"))] += 1
    lines.append("### Top 15 Organizations")
    lines.append("")
    lines.append("| Organization | Count |")
    lines.append("|-------------|-------|")
    for org, count in org_counts.most_common(15):
        lines.append(f"| {org} | {count} |")
    lines.append("")

    license_counts: Counter[str] = Counter()
    for r in records:
        license_counts[str(r.get("license", "unknown"))] += 1
    lines.append("### License Distribution")
    lines.append("")
    lines.append("| License | Count | % |")
    lines.append("|---------|-------|---|")
    for lic, count in license_counts.most_common():
        pct = count / total * 100
        lines.append(f"| {lic} | {count} | {pct:.1f}% |")
    lines.append("")

    with_text = sum(1 for r in records if r.get("full_text"))
    with_date = sum(1 for r in records if r.get("date"))
    lines.append("### Completeness")
    lines.append("")
    lines.append(f"- Records with full_text: {with_text} ({with_text / total * 100:.1f}%)")
    lines.append(f"- Records with date: {with_date} ({with_date / total * 100:.1f}%)")
    lines.append(
        f"- Records with severity: {total - sev_counts.get(-1, 0)}"
        f" ({(total - sev_counts.get(-1, 0)) / total * 100:.1f}%)"
    )

    section_counts: Counter[str] = Counter()
    for r in records:
        sections_raw = r.get("sections", "[]")
        try:
            sections = json.loads(str(sections_raw))
            for s in sections:
                section_counts[str(s)] += 1
        except (json.JSONDecodeError, TypeError):
            pass
    if section_counts:
        lines.append("")
        lines.append("### Section Coverage")
        lines.append("")
        lines.append("| Section Type | Count | % of records |")
        lines.append("|-------------|-------|-------------|")
        for sec, count in section_counts.most_common():
            pct = count / total * 100
            lines.append(f"| {sec} | {count} | {pct:.1f}% |")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dataset stats")
    parser.add_argument("--export-dir", default="data/export")
    args = parser.parse_args()

    records = load_records(args.export_dir)
    if not records:
        manifest_path = Path(args.export_dir) / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            print(f"Manifest: {json.dumps(manifest, indent=2)}")
        else:
            print("No exported dataset found. Run scripts/export_dataset.py first.")
        return

    print(generate_stats(records))


if __name__ == "__main__":
    main()
