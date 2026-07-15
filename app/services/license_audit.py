"""License audit — detect licenses from content and URLs, enforce export policy."""

from __future__ import annotations

from dataclasses import dataclass
import re

PERMISSIVE_LICENSES = frozenset(
    {
        "cc0-1.0",
        "cc-by-4.0",
        "cc-by-3.0",
        "cc-by-2.0",
        "cc-by-sa-4.0",
        "cc-by-sa-3.0",
        "apache-2.0",
        "mit",
        "bsd-2-clause",
        "bsd-3-clause",
        "unlicense",
        "public-domain",
    }
)

CC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cc0-1.0", re.compile(r"(?i)\bcc\s*0\b|creative\s+commons\s+zero|public\s+domain")),
    ("cc-by-4.0", re.compile(r"(?i)creative\s+commons\s+attribution\s+4\.0|cc[\s-]*by[\s-]*4\.0")),
    ("cc-by-3.0", re.compile(r"(?i)creative\s+commons\s+attribution\s+3\.0|cc[\s-]*by[\s-]*3\.0")),
    ("cc-by-2.0", re.compile(r"(?i)creative\s+commons\s+attribution\s+2\.0|cc[\s-]*by[\s-]*2\.0")),
    (
        "cc-by-sa-4.0",
        re.compile(
            r"(?i)creative\s+commons\s+attribution[\s-]*share\s*alike\s+4\.0"
            r"|cc[\s-]*by[\s-]*sa[\s-]*4\.0"
        ),
    ),
    (
        "cc-by-sa-3.0",
        re.compile(
            r"(?i)creative\s+commons\s+attribution[\s-]*share\s*alike\s+3\.0"
            r"|cc[\s-]*by[\s-]*sa[\s-]*3\.0"
        ),
    ),
    ("apache-2.0", re.compile(r"(?i)apache\s+license,?\s+version\s+2\.0|apache[\s-]*2\.0")),
    ("mit", re.compile(r"(?i)\bMIT\s+License\b")),
]

GITHUB_LICENSE_MAP: dict[str, str] = {
    "mit": "mit",
    "apache-2.0": "apache-2.0",
    "bsd-2-clause": "bsd-2-clause",
    "bsd-3-clause": "bsd-3-clause",
    "cc0-1.0": "cc0-1.0",
    "cc-by-4.0": "cc-by-4.0",
    "cc-by-sa-4.0": "cc-by-sa-4.0",
    "unlicense": "unlicense",
    "gpl-3.0": "gpl-3.0",
    "lgpl-3.0": "lgpl-3.0",
    "agpl-3.0": "agpl-3.0",
    "mpl-2.0": "mpl-2.0",
}


def detect_license_from_text(text: str) -> str:
    for license_id, pattern in CC_PATTERNS:
        if pattern.search(text[:5000]):
            return license_id
    return "all-rights-reserved"


def detect_license_from_github(repo_license: str | None) -> str:
    if not repo_license:
        return "all-rights-reserved"
    normalized = repo_license.lower().strip()
    return GITHUB_LICENSE_MAP.get(normalized, "all-rights-reserved")


def detect_license(
    body: str | None,
    url: str | None,
    github_license: str | None = None,
) -> str:
    if github_license:
        detected = detect_license_from_github(github_license)
        if detected != "all-rights-reserved":
            return detected
    if body:
        detected = detect_license_from_text(body)
        if detected != "all-rights-reserved":
            return detected
    return "all-rights-reserved"


def is_permissive(license_id: str) -> bool:
    return license_id in PERMISSIVE_LICENSES


@dataclass(frozen=True)
class ExportRecord:
    incident_id: str
    title: str
    full_text: str | None
    license: str


@dataclass(frozen=True)
class PolicyResult:
    incident_id: str
    include_full_text: bool
    license: str


def apply_export_policy(record: ExportRecord) -> PolicyResult:
    return PolicyResult(
        incident_id=record.incident_id,
        include_full_text=is_permissive(record.license),
        license=record.license,
    )
