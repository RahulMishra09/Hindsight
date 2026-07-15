"""Push exported dataset to HuggingFace Hub.

Usage:
    # Dry run (no upload):
    python -m scripts.push_dataset_to_hub --repo RahuL0009/hindsight-corpus --tag v0.1.0 --dry-run

    # Real push (requires HF_TOKEN env var):
    python -m scripts.push_dataset_to_hub --repo RahuL0009/hindsight-corpus --tag v0.1.0
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def push_to_hub(
    repo: str,
    tag: str,
    export_dir: str = "data/export",
    dry_run: bool = False,
) -> None:
    export_path = Path(export_dir)
    if not export_path.exists():
        print(f"Export directory {export_dir} not found. Run scripts/export_dataset.py first.")
        return

    dataset_card_src = Path("docs/dataset_card.md")

    if dry_run:
        print(f"[DRY RUN] Would push {export_dir} to {repo} (revision={tag})")
        print(f"  - Export dir: {export_path}")
        if dataset_card_src.exists():
            print(f"  - Dataset card: {dataset_card_src}")
        manifest = export_path / "manifest.json"
        if manifest.exists():
            print(f"  - Manifest: {manifest.read_text().strip()}")
        print("[DRY RUN] No upload performed.")
        return

    from huggingface_hub import HfApi

    api = HfApi()

    api.create_repo(repo_id=repo, repo_type="dataset", exist_ok=True)

    if dataset_card_src.exists():
        readme_dest = export_path / "README.md"
        shutil.copy2(dataset_card_src, readme_dest)

    api.upload_folder(
        folder_path=str(export_path),
        repo_id=repo,
        repo_type="dataset",
        commit_message=f"Release {tag}",
        revision="main",
    )

    api.create_tag(
        repo_id=repo,
        repo_type="dataset",
        tag=tag,
        tag_message=f"hindsight-corpus {tag}",
    )

    print(f"Pushed {export_dir} to https://huggingface.co/datasets/{repo} (tag={tag})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Push dataset to HuggingFace Hub")
    parser.add_argument("--repo", required=True, help="HF repo id")
    parser.add_argument("--tag", required=True, help="Version tag")
    parser.add_argument("--export-dir", default="data/export")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    push_to_hub(repo=args.repo, tag=args.tag, export_dir=args.export_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
