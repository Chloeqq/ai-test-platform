from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class DocumentFetchError(RuntimeError):
    """Raised when fetching a remote document fails."""


def _parse_payload(text: str) -> dict[str, Any] | None:
    content = str(text or "").strip()
    if not content:
        return None
    try:
        payload = json.loads(content)
        return payload if isinstance(payload, dict) else None
    except Exception:
        pass
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(content)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def fetch_document(*, url: str, timeout_seconds: int = 12) -> dict[str, Any]:
    raw_url = str(url or "").strip()
    if not raw_url:
        raise DocumentFetchError("url must not be empty")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise DocumentFetchError("only http/https urls are supported")
    try:
        request = Request(raw_url, headers={"User-Agent": "requirement-parser-agent/1.0"})
        with urlopen(request, timeout=timeout_seconds) as response:
            payload_bytes = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except (URLError, TimeoutError) as exc:
        raise DocumentFetchError(str(exc)) from exc
    except Exception as exc:
        raise DocumentFetchError(str(exc)) from exc

    text = payload_bytes.decode(charset, errors="replace").strip()
    return {
        "url": raw_url,
        "text": text,
        "parsed": _parse_payload(text),
    }

