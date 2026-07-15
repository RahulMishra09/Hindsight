"""Tests for the promoter service — org extraction, severity heuristic, date parsing, summary."""

from __future__ import annotations

from datetime import date

from app.services.promoter import (
    build_summary,
    estimate_severity,
    extract_date,
    extract_org,
)


class TestExtractOrg:
    def test_simple_domain(self) -> None:
        assert extract_org("https://engineering.shopify.com/blogs/123") == "shopify"

    def test_www_prefix_stripped(self) -> None:
        assert extract_org("https://www.google.com/incident") == "google"

    def test_blog_prefix_stripped(self) -> None:
        assert extract_org("https://blog.cloudflare.com/post") == "cloudflare"

    def test_status_prefix_stripped(self) -> None:
        assert extract_org("https://status.github.com/outage") == "github"

    def test_github_io(self) -> None:
        assert extract_org("https://mycompany.github.io/postmortem") == "mycompany"

    def test_no_url_returns_unknown(self) -> None:
        assert extract_org(None) == "unknown"

    def test_empty_url_returns_unknown(self) -> None:
        assert extract_org("") == "unknown"

    def test_co_uk_domain(self) -> None:
        assert extract_org("https://blog.acme.co.uk/incident") == "acme"


class TestEstimateSeverity:
    def test_total_outage_is_sev0(self) -> None:
        assert estimate_severity("We experienced a total outage.") == 0

    def test_data_loss_is_sev0(self) -> None:
        assert estimate_severity("There was significant data loss.") == 0

    def test_major_outage_is_sev1(self) -> None:
        assert estimate_severity("A major outage impacted users.") == 1

    def test_partial_outage_is_sev2(self) -> None:
        assert estimate_severity("We had a partial outage in region us-east-1.") == 2

    def test_degraded_is_sev2(self) -> None:
        assert estimate_severity("Service was degraded for 30 minutes.") == 2

    def test_minor_issue_is_sev3(self) -> None:
        assert estimate_severity("A minor issue was detected in monitoring.") == 3

    def test_no_keywords_returns_none(self) -> None:
        assert estimate_severity("We deployed a new feature successfully.") is None

    def test_highest_severity_wins(self) -> None:
        text = "There was a total outage and also a minor issue."
        assert estimate_severity(text) == 0


class TestExtractDate:
    def test_iso_date_in_title(self) -> None:
        assert extract_date("Incident 2024-03-15", None) == date(2024, 3, 15)

    def test_us_format_in_body(self) -> None:
        assert extract_date(None, "On 03/15/2024 we had an outage.") == date(2024, 3, 15)

    def test_long_month_in_title(self) -> None:
        assert extract_date("January 5, 2023 Postmortem", None) == date(2023, 1, 5)

    def test_long_month_no_comma(self) -> None:
        assert extract_date("March 22 2022 outage", None) == date(2022, 3, 22)

    def test_no_date_returns_none(self) -> None:
        assert extract_date("Postmortem analysis", "No date here.") is None

    def test_title_preferred_over_body(self) -> None:
        result = extract_date("Incident 2024-01-01", "On 2023-06-15 we had issues.")
        assert result == date(2024, 1, 1)

    def test_slash_date_in_title(self) -> None:
        assert extract_date("Outage 2024/07/04", None) == date(2024, 7, 4)


class TestBuildSummary:
    def test_short_text_returned_as_is(self) -> None:
        assert build_summary("Short text.") == "Short text."

    def test_none_returns_none(self) -> None:
        assert build_summary(None) is None

    def test_long_text_truncated_at_sentence(self) -> None:
        text = "First sentence. " + "x" * 600
        result = build_summary(text)
        assert result is not None
        assert result.endswith(".")
        assert len(result) <= 500

    def test_no_period_in_first_500_chars(self) -> None:
        text = "x" * 600
        result = build_summary(text)
        assert result is not None
        assert len(result) == 500
