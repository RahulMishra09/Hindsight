"""Tests for seed loader URL extraction."""

from __future__ import annotations

from app.ingest.seed_loader import extract_urls


class TestExtractUrls:
    def test_extracts_markdown_links(self):
        md = """
# Post-mortems
- [Incident 1](https://blog.example.com/postmortem-1)
- [Incident 2](https://blog.example.com/postmortem-2)
"""
        urls = extract_urls(md)
        assert urls == [
            "https://blog.example.com/postmortem-1",
            "https://blog.example.com/postmortem-2",
        ]

    def test_deduplicates_urls(self):
        md = """
- [Incident](https://blog.example.com/pm)
- [Same Incident](https://blog.example.com/pm)
"""
        urls = extract_urls(md)
        assert len(urls) == 1

    def test_strips_trailing_slash(self):
        md = "- [Test](https://example.com/page/)"
        urls = extract_urls(md)
        assert urls == ["https://example.com/page"]

    def test_skips_github_repo_links(self):
        md = """
- [Repo](https://github.com/danluu/post-mortems)
- [Real](https://blog.example.com/postmortem)
"""
        urls = extract_urls(md)
        assert urls == ["https://blog.example.com/postmortem"]

    def test_skips_badge_links(self):
        md = "[![badge](https://shields.io/badge)](https://example.com)"
        urls = extract_urls(md)
        assert "https://shields.io/badge" not in urls

    def test_handles_empty_markdown(self):
        assert extract_urls("") == []

    def test_handles_no_links(self):
        assert extract_urls("# Title\nSome text without links.") == []
