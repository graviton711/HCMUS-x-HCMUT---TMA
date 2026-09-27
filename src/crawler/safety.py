from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class UnsafeURLError(ValueError):
    """Raised when a URL could reach a non-public or out-of-scope destination."""


def normalized_origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").rstrip(".").lower()
    if scheme not in {"http", "https"} or not host:
        raise UnsafeURLError("Only absolute HTTP(S) URLs are accepted")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs containing credentials are not accepted")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeURLError("URL contains an invalid port") from exc
    return scheme, host, port


def validate_public_url(url: str, expected_origin: tuple[str, str, int] | None = None) -> str:
    origin = normalized_origin(url)
    if expected_origin is not None and origin != expected_origin:
        raise UnsafeURLError("Cross-origin URL is outside the crawl scope")

    host = origin[1]
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            records = socket.getaddrinfo(host, origin[2], type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeURLError(f"Could not resolve host: {host}") from exc
        addresses = []
        for record in records:
            try:
                addresses.append(ipaddress.ip_address(record[4][0]))
            except ValueError:
                continue

    if not addresses:
        raise UnsafeURLError(f"Host did not resolve to an IP address: {host}")
    if any(not address.is_global for address in addresses):
        raise UnsafeURLError("Local, private, reserved, and non-public IPs are blocked")

    parts = urlsplit(url)
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc, path, parts.query, ""))
