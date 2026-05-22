from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit


def _is_loopback_host(hostname: str | None) -> bool:
    return str(hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}


def _rewrite_loopback_url_for_runner(expected_url: str, *, base_url: str) -> str:
    parsed_expected = urlsplit(expected_url)
    if not parsed_expected.scheme or not parsed_expected.netloc:
        return expected_url
    mapped_url = _rewrite_by_origin_map(expected_url)
    if mapped_url != expected_url:
        return mapped_url
    if not _is_loopback_host(parsed_expected.hostname):
        return expected_url

    runner_loopback_host = os.getenv("RUNNER_LOOPBACK_HOST", "").strip()
    if runner_loopback_host:
        netloc = runner_loopback_host
        if parsed_expected.port:
            netloc = f"{runner_loopback_host}:{parsed_expected.port}"
        return urlunsplit(
            (
                parsed_expected.scheme,
                netloc,
                parsed_expected.path or "/",
                parsed_expected.query,
                parsed_expected.fragment,
            )
        )
    return expected_url


def _rewrite_by_origin_map(expected_url: str) -> str:
    rewrite_map = os.getenv("RUNNER_URL_REWRITE_MAP", "").strip()
    if not rewrite_map:
        return expected_url
    parsed_expected = urlsplit(expected_url)
    expected_origin = f"{parsed_expected.scheme}://{parsed_expected.netloc}"
    for item in rewrite_map.replace("\n", ";").split(";"):
        if not item.strip() or "=" not in item:
            continue
        raw_from, raw_to = item.split("=", 1)
        from_origin = raw_from.strip().rstrip("/")
        to_origin = raw_to.strip().rstrip("/")
        if not from_origin or not to_origin or expected_origin != from_origin:
            continue
        parsed_to = urlsplit(to_origin)
        if not parsed_to.scheme or not parsed_to.netloc:
            continue
        return urlunsplit(
            (
                parsed_to.scheme,
                parsed_to.netloc,
                parsed_expected.path or "/",
                parsed_expected.query,
                parsed_expected.fragment,
            )
        )
    return expected_url


def normalize_url_for_runner(expected_url: str, *, base_url: str = "") -> str:
    normalized_expected = str(expected_url or "").strip()
    if not normalized_expected:
        return ""
    normalized_base = str(base_url or "").strip()
    if normalized_expected.startswith(("http://", "https://")):
        return _rewrite_loopback_url_for_runner(normalized_expected, base_url=normalized_base)
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
