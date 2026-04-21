from __future__ import annotations

from urllib.parse import urlsplit


def normalize_url_for_runner(expected_url: str, *, base_url: str = "") -> str:
    normalized_expected = str(expected_url or "").strip()
    if not normalized_expected:
        return ""
    if normalized_expected.startswith(("http://", "https://")):
        return normalized_expected

    normalized_base = str(base_url or "").strip()
    if not normalized_base:
        return normalized_expected

    parsed_base = urlsplit(normalized_base)
    if not parsed_base.scheme or not parsed_base.netloc:
        return normalized_expected
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    # Hash-router apps often pass "/path" as expectation.
    if normalized_expected.startswith("/"):
        if str(parsed_base.fragment or "").startswith("/"):
            return f"{origin}/#{normalized_expected}"
        return f"{origin}{normalized_expected}"

    return normalized_expected
