from __future__ import annotations

import json
import logging
import os
import urllib.request

_logger = logging.getLogger(__name__)

_API_BASE_URL = os.environ.get("PAGE_OBJECT_API_URL", "http://localhost:8000").rstrip("/")


def _load_page_object_from_api(page_name: str, project: str = "atp", client: str = "web") -> dict | None:
    """Fetch page object from the DB-backed REST API. Returns None on any failure."""
    try:
        url = f"{_API_BASE_URL}/api/page-objects/{page_name}?project_code={project}&client={client}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        item = data.get("item") if isinstance(data, dict) else None
        if not isinstance(item, dict):
            return None
        elements_raw = item.get("elements") if isinstance(item.get("elements"), list) else []
        elements: dict[str, dict] = {}
        for elem in elements_raw:
            if not isinstance(elem, dict):
                continue
            code = str(elem.get("element_code", "")).strip()
            if not code:
                continue
            elements[code] = {
                "locator_type": str(elem.get("locator_type", "css")).strip(),
                "locator_value": str(elem.get("locator_value", "")).strip(),
                "role": str(elem.get("role", "")).strip(),
            }
        if not elements:
            return None
        return {"page": page_name, "elements": elements}
    except Exception:
        _logger.debug("API page-object fetch failed for %s", page_name, exc_info=True)
        return None


def load_page_object(page_name: str) -> dict:
    """Load page object from DB API (single source of truth)."""
    api_result = _load_page_object_from_api(page_name)
    if api_result is not None:
        return api_result
    raise FileNotFoundError(f"Page object not found in DB API for page: {page_name}")


def list_page_elements(page_name: str) -> list[str]:
    page_object = load_page_object(page_name)
    elements = page_object.get("elements", {})
    return list(elements.keys())
