from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .safety import UnsafeURLError, validate_public_url


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(slots=True)
class FetchResult:
    url: str
    status_code: int
    content_type: str
    body: bytes
    error: str | None = None
    redirect_to: str | None = None


class SafeFetcher:
    def __init__(self, timeout: float = 12.0, max_bytes: int = 1_000_000, delay: float = 1.0):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.delay = delay
        self._last_request = 0.0
        self._opener = build_opener(_NoRedirect())

    def fetch(self, url: str, origin: tuple[str, str, int]) -> FetchResult:
        current = validate_public_url(url, origin)
        wait_for = self.delay - (time.monotonic() - self._last_request)
        if wait_for > 0:
            time.sleep(wait_for)
        request = Request(
            current,
            headers={
                "User-Agent": "MLAITourSourceAuditor/0.1",
                "Accept": "text/html,application/json,application/xml,text/xml,*/*;q=0.5",
            },
        )
        self._last_request = time.monotonic()
        try:
            response = self._opener.open(request, timeout=self.timeout)
            with response:
                return self._read_response(current, response.status, response.headers, response)
        except HTTPError as exc:
            content_type = exc.headers.get("Content-Type", "")
            location = exc.headers.get("Location")
            exc.close()
            if exc.code in {301, 302, 303, 307, 308}:
                if not location:
                    return FetchResult(
                        current, exc.code, content_type, b"", "Redirect without Location"
                    )
                return FetchResult(current, exc.code, content_type, b"", redirect_to=location)
            return FetchResult(current, exc.code, content_type, b"", f"HTTP {exc.code}")
        except (URLError, TimeoutError, OSError, UnsafeURLError) as exc:
            return FetchResult(current, 0, "", b"", str(exc))

    def _read_response(self, url, status, headers, stream) -> FetchResult:
        content_type = headers.get("Content-Type", "")
        length = headers.get("Content-Length")
        if length:
            try:
                if int(length) > self.max_bytes:
                    return FetchResult(
                        url, status, content_type, b"", "Response exceeds byte limit"
                    )
            except ValueError:
                pass
        data = stream.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            return FetchResult(url, status, content_type, b"", "Response exceeds byte limit")
        return FetchResult(url, status, content_type, data)
