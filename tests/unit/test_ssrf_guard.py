"""Tests for SSRF guard."""

from __future__ import annotations

import pytest

from app.ingest.ssrf_guard import SSRFBlockedError, validate_url


class TestSSRFGuard:
    async def test_public_url_allowed(self):
        result = await validate_url("https://example.com/postmortem")
        assert result == "https://example.com/postmortem"

    async def test_http_allowed(self):
        result = await validate_url("http://example.com/page")
        assert result == "http://example.com/page"

    async def test_ftp_blocked(self):
        with pytest.raises(SSRFBlockedError, match="Blocked scheme"):
            await validate_url("ftp://example.com/file")

    async def test_file_scheme_blocked(self):
        with pytest.raises(SSRFBlockedError, match="Blocked scheme"):
            await validate_url("file:///etc/passwd")

    async def test_no_hostname_blocked(self):
        with pytest.raises(SSRFBlockedError):
            await validate_url("http://")

    async def test_localhost_blocked(self):
        with pytest.raises(SSRFBlockedError, match="private"):
            await validate_url("http://127.0.0.1/admin")

    async def test_private_10_blocked(self):
        with pytest.raises(SSRFBlockedError, match="private"):
            await validate_url("http://10.0.0.1/internal")

    async def test_private_172_blocked(self):
        with pytest.raises(SSRFBlockedError, match="private"):
            await validate_url("http://172.16.0.1/internal")

    async def test_private_192_blocked(self):
        with pytest.raises(SSRFBlockedError, match="private"):
            await validate_url("http://192.168.1.1/internal")

    async def test_link_local_blocked(self):
        with pytest.raises(SSRFBlockedError, match="private"):
            await validate_url("http://169.254.169.254/metadata")

    async def test_dns_failure_blocked(self):
        with pytest.raises(SSRFBlockedError, match="DNS resolution failed"):
            await validate_url("http://nonexistent.invalid.domain.test/page")
