"""Tests for license detection and export policy."""

from __future__ import annotations

from app.services.license_audit import (
    ExportRecord,
    apply_export_policy,
    detect_license,
    detect_license_from_github,
    detect_license_from_text,
    is_permissive,
)


class TestDetectLicenseFromText:
    def test_cc0(self) -> None:
        assert detect_license_from_text("This is CC0 licensed content.") == "cc0-1.0"

    def test_creative_commons_zero(self) -> None:
        text = "Licensed under Creative Commons Zero."
        assert detect_license_from_text(text) == "cc0-1.0"

    def test_cc_by_4(self) -> None:
        text = "This work is under CC BY 4.0 license."
        assert detect_license_from_text(text) == "cc-by-4.0"

    def test_creative_commons_attribution_4(self) -> None:
        text = "Creative Commons Attribution 4.0 International License."
        assert detect_license_from_text(text) == "cc-by-4.0"

    def test_cc_by_sa_4(self) -> None:
        text = "Licensed under CC-BY-SA-4.0."
        assert detect_license_from_text(text) == "cc-by-sa-4.0"

    def test_apache_2(self) -> None:
        text = "Licensed under Apache License, Version 2.0."
        assert detect_license_from_text(text) == "apache-2.0"

    def test_mit_license(self) -> None:
        text = "Released under the MIT License."
        assert detect_license_from_text(text) == "mit"

    def test_no_license_found(self) -> None:
        text = "This is a regular postmortem with no license info."
        assert detect_license_from_text(text) == "all-rights-reserved"

    def test_public_domain(self) -> None:
        text = "This document is in the public domain."
        assert detect_license_from_text(text) == "cc0-1.0"


class TestDetectLicenseFromGithub:
    def test_mit(self) -> None:
        assert detect_license_from_github("MIT") == "mit"

    def test_apache(self) -> None:
        assert detect_license_from_github("Apache-2.0") == "apache-2.0"

    def test_unknown(self) -> None:
        assert detect_license_from_github("some-custom-license") == "all-rights-reserved"

    def test_none(self) -> None:
        assert detect_license_from_github(None) == "all-rights-reserved"

    def test_gpl(self) -> None:
        assert detect_license_from_github("GPL-3.0") == "gpl-3.0"


class TestDetectLicense:
    def test_github_license_preferred(self) -> None:
        result = detect_license(body="MIT License text", url=None, github_license="Apache-2.0")
        assert result == "apache-2.0"

    def test_falls_back_to_text(self) -> None:
        result = detect_license(body="Licensed under CC BY 4.0.", url=None)
        assert result == "cc-by-4.0"

    def test_no_signals_returns_all_rights_reserved(self) -> None:
        result = detect_license(body="Just some text.", url=None)
        assert result == "all-rights-reserved"

    def test_none_body(self) -> None:
        result = detect_license(body=None, url=None)
        assert result == "all-rights-reserved"


class TestIsPermissive:
    def test_cc0_is_permissive(self) -> None:
        assert is_permissive("cc0-1.0") is True

    def test_mit_is_permissive(self) -> None:
        assert is_permissive("mit") is True

    def test_all_rights_reserved_is_not(self) -> None:
        assert is_permissive("all-rights-reserved") is False

    def test_gpl_is_not_permissive(self) -> None:
        assert is_permissive("gpl-3.0") is False


class TestExportPolicy:
    def test_permissive_includes_full_text(self) -> None:
        record = ExportRecord(
            incident_id="abc", title="Test", full_text="body text", license="cc-by-4.0"
        )
        result = apply_export_policy(record)
        assert result.include_full_text is True

    def test_non_permissive_excludes_full_text(self) -> None:
        record = ExportRecord(
            incident_id="abc", title="Test", full_text="body text", license="all-rights-reserved"
        )
        result = apply_export_policy(record)
        assert result.include_full_text is False

    def test_policy_preserves_license(self) -> None:
        record = ExportRecord(incident_id="abc", title="Test", full_text=None, license="mit")
        result = apply_export_policy(record)
        assert result.license == "mit"
        assert result.include_full_text is True
