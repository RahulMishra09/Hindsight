"""Promoter service — converts DEDUPED documents into incident rows."""

from __future__ import annotations

from datetime import date
import re
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)

SUMMARY_MAX_CHARS = 500

SEV_KEYWORDS: list[tuple[int, re.Pattern[str]]] = [
    (0, re.compile(r"(?i)\b(total\s+outage|complete\s+outage|data\s+loss|data\s+breach)\b")),
    (1, re.compile(r"(?i)\b(major\s+outage|significant\s+impact|service\s+down)\b")),
    (2, re.compile(r"(?i)\b(partial\s+outage|degraded|elevated\s+error|latency\s+spike)\b")),
    (3, re.compile(r"(?i)\b(minor\s+issue|intermittent|brief\s+disruption)\b")),
]

DATE_RE = re.compile(
    r"(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4})"
    r"|(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})"
    r"|(?:\d{1,2}[-/]\d{1,2}[-/]\d{4})",
)

MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def extract_org(url: str | None) -> str:
    if not url:
        return "unknown"
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    for prefix in ("www.", "blog.", "status.", "engineering.", "tech."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-1] in ("io", "com") and parts[-2] in ("github", "gitlab"):
        return parts[0]
    if len(parts) >= 2:
        tld = parts[-1]
        sld = parts[-2]
        if sld in ("co", "com", "org", "io", "net") and len(parts) >= 3:
            return parts[-3]
        if tld in ("com", "org", "io", "net", "dev", "uk", "de"):
            return sld
        return sld
    return host or "unknown"


def estimate_severity(text: str) -> int | None:
    for sev, pattern in SEV_KEYWORDS:
        if pattern.search(text[:5000]):
            return sev
    return None


def extract_date(title: str | None, body: str | None) -> date | None:
    for text in [title, body]:
        if not text:
            continue
        search_text = text[:2000] if text == body else text
        match = DATE_RE.search(search_text)
        if match:
            return _parse_date_str(match.group(0))
    return None


def _parse_date_str(s: str) -> date | None:
    s = s.strip().replace(",", "")
    if re.match(r"\d{4}[-/]", s):
        parts = re.split(r"[-/]", s)
        try:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
    if re.match(r"\d{1,2}[-/]", s):
        parts = re.split(r"[-/]", s)
        try:
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return None
    parts_text = s.split()
    if len(parts_text) >= 3:
        month_name = parts_text[0].lower()
        month = MONTH_MAP.get(month_name)
        if month:
            try:
                day = int(parts_text[1])
                year = int(parts_text[2])
                return date(year, month, day)
            except (ValueError, IndexError):
                return None
    return None


def build_summary(body: str | None) -> str | None:
    if not body:
        return None
    text = body[:SUMMARY_MAX_CHARS].strip()
    last_period = text.rfind(".")
    if last_period > 0:
        text = text[: last_period + 1]
    return text
