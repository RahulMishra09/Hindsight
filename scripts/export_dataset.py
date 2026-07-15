"""Export hindsight-corpus as a HuggingFace DatasetDict.

Usage:
    python -m scripts.export_dataset --output-dir data/export
    python -m scripts.export_dataset --output-dir data/export --version v0.1.0
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.db import create_engine, create_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.repositories.incident import IncidentRepository
from app.services.license_audit import is_permissive

logger = get_logger(__name__)


def _get_git_tag() -> str:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return "dev"


async def _fetch_incidents(batch_size: int = 5000) -> list[dict[str, object]]:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)

    records: list[dict[str, object]] = []
    try:
        sm = create_sessionmaker(engine)
        async with sm() as session:
            repo = IncidentRepository(session)
            incidents = await repo.list_all(limit=batch_size)

            for inc in incidents:
                include_text = is_permissive(inc.license)
                records.append(
                    {
                        "id": str(inc.id),
                        "org": inc.org,
                        "title": inc.title,
                        "url": inc.url or "",
                        "date": inc.occurred_on.isoformat() if inc.occurred_on else "",
                        "severity": inc.severity if inc.severity is not None else -1,
                        "sections": json.dumps(inc.sections) if inc.sections else "[]",
                        "license": inc.license,
                        "full_text": (inc.summary or "") if include_text else "",
                        "content_hash": inc.content_hash,
                    }
                )
    finally:
        await engine.dispose()

    records.sort(key=lambda r: str(r["content_hash"]))
    return records


def build_dataset(records: list[dict[str, object]], version: str) -> Any:
    import datasets

    ds = datasets.Dataset.from_list(records)
    ds_dict = datasets.DatasetDict({"train": ds})
    ds_dict = ds_dict.cast_column(
        "severity",
        datasets.Value("int32"),
    )

    info = datasets.DatasetInfo(
        description="Hindsight incident corpus — cleaned, license-audited postmortems.",
        version=version,
        license="Apache-2.0",
    )
    ds_dict["train"].info = info
    return ds_dict


def compute_manifest_hash(output_dir: Path) -> str:
    h = hashlib.sha256()
    parquet_files = sorted(output_dir.rglob("*.parquet"))
    for f in parquet_files:
        h.update(f.read_bytes())
    return h.hexdigest()


def export(output_dir: str, version: str | None = None) -> Path:
    ver = version or _get_git_tag()
    records = asyncio.run(_fetch_incidents())

    if not records:
        logger.warning("export.no_records")
        print("No incidents to export.")
        return Path(output_dir)

    ds_dict = build_dataset(records, ver)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ds_dict.save_to_disk(str(out))

    manifest_hash = compute_manifest_hash(out)
    manifest = {
        "version": ver,
        "num_records": len(records),
        "sha256": manifest_hash,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    logger.info(
        "export.done",
        version=ver,
        records=len(records),
        sha256=manifest_hash[:16],
        output=str(out),
    )
    print(f"Exported {len(records)} records (version={ver}, sha256={manifest_hash[:16]}...)")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Export hindsight-corpus dataset")
    parser.add_argument("--output-dir", default="data/export", help="Output directory")
    parser.add_argument("--version", default=None, help="Dataset version (default: git tag)")
    args = parser.parse_args()
    export(output_dir=args.output_dir, version=args.version)


if __name__ == "__main__":
    main()
