"""SSRF guard — blocks requests to private/loopback/link-local addresses."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


class SSRFBlockedError(Exception):
    pass


async def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFBlockedError(f"Blocked scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFBlockedError("No hostname in URL")

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None, family=socket.AF_UNSPEC)
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"DNS resolution failed: {hostname}") from exc

    for _family, _type, _proto, _canonname, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise SSRFBlockedError(f"Blocked private/reserved IP: {ip}")

    return url
