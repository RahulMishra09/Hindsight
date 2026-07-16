"""Unit tests for annotation sampler and template rendering."""

from dataclasses import dataclass
from datetime import date

from app.annotation.sampler import stratified_sample
from app.annotation.templates import (
    SHORTCUTS,
    render_done_page,
    render_incident_card,
    render_progress_bar,
)
from app.models.incident_label import TAXONOMY_LABELS


@dataclass
class FakeIncident:
    id: str
    title: str = "Test incident"
    org: str = "acme"
    summary: str = "Something broke"
    sections: list[str] | None = None
    severity: int | None = 1
    occurred_on: date | None = None


class TestStratifiedSample:
    def test_returns_up_to_n(self):
        incidents = [FakeIncident(id=str(i)) for i in range(10)]
        silver = {str(i): ["dns"] for i in range(10)}
        result = stratified_sample(incidents, silver, 5)
        assert len(result) == 5

    def test_excludes_annotated(self):
        incidents = [FakeIncident(id=str(i)) for i in range(5)]
        silver = {str(i): ["dns"] for i in range(5)}
        result = stratified_sample(incidents, silver, 5, annotated_ids={"0", "1", "2"})
        ids = {str(inc.id) for inc in result}
        assert "0" not in ids
        assert "1" not in ids

    def test_rare_labels_prioritized(self):
        incidents = [FakeIncident(id=str(i)) for i in range(20)]
        silver: dict[str, list[str]] = {}
        for i in range(15):
            silver[str(i)] = ["bad-deploy"]
        silver["15"] = ["certificate-expiry"]
        silver["16"] = ["thundering-herd"]
        result = stratified_sample(incidents, silver, 5, seed=42)
        sampled_ids = {str(inc.id) for inc in result}
        assert "15" in sampled_ids or "16" in sampled_ids

    def test_empty_incidents(self):
        result = stratified_sample([], {}, 5)
        assert result == []

    def test_deterministic_with_seed(self):
        incidents = [FakeIncident(id=str(i)) for i in range(20)]
        silver = {str(i): ["dns"] for i in range(20)}
        r1 = stratified_sample(incidents, silver, 5, seed=123)
        r2 = stratified_sample(incidents, silver, 5, seed=123)
        assert [str(i.id) for i in r1] == [str(i.id) for i in r2]


class TestProgressBar:
    def test_renders_percentage(self):
        html = render_progress_bar(25, 100)
        assert "25%" in html
        assert "25/100" in html

    def test_zero_total(self):
        html = render_progress_bar(0, 0)
        assert "0%" in html


class TestIncidentCard:
    def test_renders_title(self):
        inc = FakeIncident(id="abc", title="Major DNS Outage")
        html = render_incident_card(inc, "user1", 0, 10, set(), set())
        assert "Major DNS Outage" in html

    def test_renders_labels_grid(self):
        inc = FakeIncident(id="abc")
        html = render_incident_card(inc, "user1", 0, 10, {"dns"}, set())
        assert 'name="label_dns"' in html
        assert "silver-dot" in html

    def test_renders_existing_checked(self):
        inc = FakeIncident(id="abc")
        html = render_incident_card(inc, "user1", 0, 10, set(), {"dns"})
        assert "checked" in html


class TestDonePage:
    def test_renders_count(self):
        html = render_done_page(50, 100, "user1")
        assert "50/100" in html
        assert "user1" in html


class TestShortcuts:
    def test_all_labels_have_shortcuts(self):
        for label in TAXONOMY_LABELS:
            assert label in SHORTCUTS

    def test_shortcuts_are_unique(self):
        values = list(SHORTCUTS.values())
        assert len(values) == len(set(values))
