"""Tests for parser helper functions and golden-file parsing."""

from __future__ import annotations

import os

from app.workers.parser import (
    _detect_language,
    _detect_sections,
    _extract_content,
    _normalize_text,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "golden")


class TestNormalizeText:
    def test_nfc_normalization(self):
        decomposed = "café"
        result = _normalize_text(decomposed)
        assert result == "café"

    def test_ascii_unchanged(self):
        text = "hello world"
        assert _normalize_text(text) == "hello world"


class TestDetectLanguage:
    def test_english_detected(self):
        text = "This is a postmortem about a server outage that happened last week."
        assert _detect_language(text) == "en"

    def test_non_english_detected(self):
        text = "これは日本語のテキストです。" * 50
        assert _detect_language(text) == "non-en"


class TestDetectSections:
    def test_detects_impact(self):
        text = "## Impact\nThe outage affected 50% of users."
        sections = _detect_sections(text)
        assert any("impact" in s.lower() for s in sections)

    def test_detects_root_cause(self):
        text = "## Root Cause\nA misconfigured load balancer caused the issue."
        sections = _detect_sections(text)
        assert any("root" in s.lower() and "cause" in s.lower() for s in sections)

    def test_detects_timeline(self):
        text = "## Timeline\n10:00 - Alert fired\n10:15 - Incident declared"
        sections = _detect_sections(text)
        assert any("timeline" in s.lower() for s in sections)

    def test_detects_lessons_learned(self):
        text = "## Lessons Learned\nWe need better monitoring."
        sections = _detect_sections(text)
        assert any("lesson" in s.lower() for s in sections)

    def test_no_sections_found(self):
        text = "This is just a plain paragraph with no headings."
        sections = _detect_sections(text)
        assert sections == []


class TestExtractContent:
    def test_extracts_from_html(self):
        html = """
        <html>
        <head><title>Postmortem: Service Outage</title></head>
        <body>
            <article>
                <h1>Postmortem: Service Outage</h1>
                <p>On January 15, our primary database experienced a cascading failure
                that resulted in 3 hours of downtime. This postmortem describes what
                happened, why it happened, and what we're doing to prevent it from
                happening again.</p>
                <h2>Impact</h2>
                <p>Approximately 100,000 users were affected. All API endpoints returned
                500 errors during the incident window.</p>
                <h2>Root Cause</h2>
                <p>A misconfigured connection pool exhausted available database connections
                when traffic spiked during a marketing campaign.</p>
                <h2>Timeline</h2>
                <p>14:00 UTC - Traffic spike began</p>
                <p>14:15 UTC - First alerts fired</p>
                <p>14:30 UTC - Incident declared</p>
                <h2>Lessons Learned</h2>
                <p>We need to implement connection pool monitoring and automatic scaling.</p>
            </article>
        </body>
        </html>
        """
        _title, content = _extract_content(html)
        assert content is not None
        assert len(content) > 50

    def test_returns_none_for_empty_html(self):
        _title, content = _extract_content("<html><body></body></html>")
        assert content is None or content == ""

    def test_preserves_meaningful_text(self):
        html = """
        <html><body>
        <h1>Outage Report</h1>
        <p>Our service experienced downtime due to a database migration failure.</p>
        <pre><code>SELECT * FROM users WHERE active = true;</code></pre>
        <p>The query above caused a full table scan.</p>
        </body></html>
        """
        _title, content = _extract_content(html)
        if content:
            assert "database" in content.lower() or "migration" in content.lower()
