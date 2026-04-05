from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from .case_dictionary import get_alias_code_map, get_code_name_map, get_enabled_codes, resolve_dictionary_code


DEFAULT_PROJECT = "atp"
DEFAULT_CLIENT = "web"
DEFAULT_CASE_TYPE = "fn"
DEFAULT_SOURCE = "ai"
DEFAULT_CASE_ID = "atp-web-common-core-fn-ai-0001"

CLIENT_CODES = get_enabled_codes("client")
CASE_TYPE_CODES = get_enabled_codes("case_type")
SOURCE_CODES = get_enabled_codes("source")

PAGE_CODE_MAP = {alias: code.upper() for alias, code in get_alias_code_map("page").items()}
PAGE_NAME_MAP = {code.upper(): name for code, name in get_code_name_map("page").items()}
MODULE_CODE_MAP = {alias: code.upper() for alias, code in get_alias_code_map("module").items()}
MODULE_NAME_MAP = {code.upper(): name for code, name in get_code_name_map("module").items()}
CASE_TYPE_NAME_MAP = {code.upper(): name for code, name in get_code_name_map("case_type").items()}
SOURCE_NAME_MAP = {code.upper(): name for code, name in get_code_name_map("source").items()}

_CASE_ID_PATTERN = re.compile(
    r"^(?P<project>[a-z0-9]{2,10})-"
    r"(?P<client>web|app|api|admin|h5)-"
    r"(?P<page>[a-z0-9]{3,8})-"
    r"(?P<module>[a-z0-9]{3,8})-"
    r"(?P<case_type>sm|rg|fn|ex|int|e2e)-"
    r"(?P<source>ai|mn|cv|imp|fb)-"
    r"(?P<sequence>\d{4})$"
    , re.IGNORECASE
)


def slugify_case_part(value: str, *, fallback: str = "general") -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip()).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return normalized or fallback


def _to_code(value: str, *, fallback: str, min_len: int = 3, max_len: int = 8) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip()).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    if not cleaned:
        return fallback
    direct = cleaned.replace("-", "").upper()
    if min_len <= len(direct) <= max_len:
        return direct
    parts = [part for part in cleaned.split("-") if part]
    acronym = "".join(part[:3].upper() for part in parts)
    if min_len <= len(acronym) <= max_len:
        return acronym
    initials = "".join(part[0].upper() for part in parts if part)
    if len(initials) >= min_len:
        return initials[:max_len]
    padded = (direct + fallback).upper()
    return padded[:max_len]


def _as_text_list(values: Any) -> list[str]:
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    if isinstance(values, tuple):
        return [str(item).strip() for item in values if str(item).strip()]
    if isinstance(values, set):
        return [str(item).strip() for item in values if str(item).strip()]
    if isinstance(values, str) and values.strip():
        return [values.strip()]
    return []


def build_case_prefix(
    *,
    project: str = DEFAULT_PROJECT,
    client: str = DEFAULT_CLIENT,
    page_code: str,
    module_code: str,
    case_type: str = DEFAULT_CASE_TYPE,
    source: str = DEFAULT_SOURCE,
) -> str:
    normalized_project = _to_code(project, fallback=DEFAULT_PROJECT, min_len=2, max_len=10).lower()
    normalized_client = normalize_client_code(client)
    normalized_page = normalize_page_code(page_code)
    normalized_module = normalize_module_code(module_code)
    normalized_type = normalize_case_type(case_type)
    normalized_source = normalize_source_code(source)
    return "-".join(
        [
            normalized_project,
            normalized_client,
            normalized_page,
            normalized_module,
            normalized_type,
            normalized_source,
        ]
    ).lower()


def build_case_id(
    *,
    page: str = "",
    module: str = "",
    sequence: int,
    project: str = DEFAULT_PROJECT,
    client: str = DEFAULT_CLIENT,
    page_code: str = "",
    module_code: str = "",
    case_type: str = DEFAULT_CASE_TYPE,
    source: str = DEFAULT_SOURCE,
) -> str:
    resolved_page_code = page_code or infer_page_code(page)
    resolved_module_code = module_code or infer_module_code(page=page, module=module)
    prefix = build_case_prefix(
        project=project,
        client=client,
        page_code=resolved_page_code,
        module_code=resolved_module_code,
        case_type=case_type,
        source=source,
    )
    normalized_sequence = max(1, int(sequence))
    return f"{prefix}-{normalized_sequence:04d}"


def match_case_id(value: str) -> re.Match[str] | None:
    return _CASE_ID_PATTERN.match(str(value or "").strip())


def split_run_id(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if ":" not in text:
        return text, ""
    case_id, started_at = text.split(":", 1)
    return case_id.strip(), started_at.strip()


def normalize_client_code(value: str, *, fallback: str = DEFAULT_CLIENT) -> str:
    code = _to_code(value, fallback=fallback, min_len=2, max_len=5).lower()
    return code if code in CLIENT_CODES else fallback


def infer_client_code(value: str = "", *, runner: str = "") -> str:
    corpus = " ".join([str(value or "").strip(), str(runner or "").strip()]).lower()
    if "mobile" in corpus or "app" in corpus:
        return "app"
    if "api" in corpus:
        return "api"
    if "admin" in corpus:
        return "admin"
    if "h5" in corpus:
        return "h5"
    return "web"


def normalize_case_type(value: str, *, fallback: str = DEFAULT_CASE_TYPE) -> str:
    code = _to_code(value, fallback=fallback, min_len=2, max_len=3).lower()
    return code if code in CASE_TYPE_CODES else fallback


def normalize_source_code(value: str, *, fallback: str = DEFAULT_SOURCE) -> str:
    code = _to_code(value, fallback=fallback, min_len=2, max_len=3).lower()
    return code if code in SOURCE_CODES else fallback


def normalize_page_code(value: str, *, fallback: str = "COMMON") -> str:
    resolved = resolve_dictionary_code("page", value, fallback="")
    if resolved:
        return resolved.lower()
    return _to_code(value, fallback=fallback, min_len=3, max_len=8).lower()


def normalize_module_code(value: str, *, fallback: str = "CORE") -> str:
    resolved = resolve_dictionary_code("module", value, fallback="")
    if resolved:
        return resolved.lower()
    return _to_code(value, fallback=fallback, min_len=3, max_len=8).lower()


def infer_page_code(page: str, *, title: str = "", tags: Any = None) -> str:
    resolved = resolve_dictionary_code("page", page, fallback="")
    if resolved:
        return resolved
    corpus = " ".join([page, title, *(_as_text_list(tags))]).lower()
    if "return" in corpus:
        return "ret"
    if "refund" in corpus:
        return "ref"
    if "login" in corpus or "auth" in corpus:
        return "login"
    if "order" in corpus:
        return "ord"
    if "product" in corpus:
        return "prod"
    return normalize_page_code(page or title or "common")


def infer_module_code(
    *,
    page: str,
    module: str = "",
    title: str = "",
    tags: Any = None,
    steps: Any = None,
) -> str:
    resolved = resolve_dictionary_code("module", module, fallback="")
    if resolved:
        return resolved
    text_bits = [page, module, title, *(_as_text_list(tags))]
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                text_bits.append(str(step.get("action", "")).strip())
                text_bits.append(str(step.get("target", "")).strip())
    corpus = " ".join(bit for bit in text_bits if bit).lower()
    if any(token in corpus for token in ["auth", "login", "password"]):
        return "auth"
    if any(token in corpus for token in ["search", "query", "keyword", "filter"]):
        return "query"
    if any(token in corpus for token in ["list", "table", "grid"]):
        return "list"
    if any(token in corpus for token in ["detail", "info"]):
        return "detail"
    if any(token in corpus for token in ["submit", "save", "create", "apply", "form"]):
        return "subm"
    if any(token in corpus for token in ["upload", "image", "picture"]):
        return "upld"
    if any(token in corpus for token in ["calc", "amount", "price", "refund"]):
        return "calc"
    fallback = normalize_module_code(module or page, fallback="CORE")
    if fallback == infer_page_code(page, title=title, tags=tags):
        return "core"
    return fallback


def infer_case_type(
    *,
    title: str = "",
    description: str = "",
    tags: Any = None,
) -> str:
    corpus = " ".join([title, description, *(_as_text_list(tags))]).lower()
    if any(token in corpus for token in ["exception", "error", "invalid", "security", "sql", "异常"]):
        return "ex"
    if any(token in corpus for token in ["regression", "回归"]):
        return "rg"
    if "integration" in corpus:
        return "int"
    if "e2e" in corpus:
        return "e2e"
    if "smoke" in corpus:
        return "sm"
    return "fn"


def infer_source_code(*, tags: Any = None, source_hint: str = "", legacy: bool = False) -> str:
    corpus = " ".join([source_hint, *(_as_text_list(tags))]).lower()
    if legacy:
        return "imp"
    if "review" in corpus or "manual-reviewed" in corpus:
        return "cv"
    if "fallback" in corpus:
        return "fb"
    if "ai-generated" in corpus or "generated" in corpus:
        return "ai"
    return "mn"


def normalize_case_id(value: str, *, fallback: str = DEFAULT_CASE_ID) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    canonical = re.sub(r"[^A-Za-z0-9:-]+", "-", raw).strip("-")
    if ":" in canonical:
        case_part, started_at = split_run_id(canonical)
        normalized_case = normalize_case_id(case_part, fallback=fallback)
        return f"{normalized_case}:{started_at}" if started_at else normalized_case
    lowercase = canonical.lower()
    if match_case_id(lowercase):
        return lowercase
    parts = [part for part in re.split(r"[-_]", canonical) if part]
    if len(parts) >= 3 and parts[-1].isdigit():
        lead = parts[0].lower()
        if lead in {"tc", "case", "test"} and len(parts) >= 3:
            page = parts[1]
            module = "-".join(parts[2:-1]) or parts[1]
        else:
            page = parts[0]
            module = "-".join(parts[1:-1]) or page
        sequence = int(parts[-1])
        return build_case_id(
            page=page,
            module=module,
            sequence=sequence,
            case_type=DEFAULT_CASE_TYPE,
            source=DEFAULT_SOURCE,
        )
    return fallback


def next_case_sequence(
    *,
    existing_case_ids: Iterable[str],
    page: str = "",
    module: str = "",
    project: str = DEFAULT_PROJECT,
    client: str = DEFAULT_CLIENT,
    page_code: str = "",
    module_code: str = "",
    case_type: str = DEFAULT_CASE_TYPE,
    source: str = DEFAULT_SOURCE,
) -> int:
    prefix = build_case_prefix(
        project=project,
        client=client,
        page_code=page_code or infer_page_code(page),
        module_code=module_code or infer_module_code(page=page, module=module),
        case_type=case_type,
        source=source,
    )
    highest = 0
    for raw in existing_case_ids:
        match = match_case_id(str(raw or "").strip())
        if not match:
            continue
        candidate_prefix = "-".join(
            [
                match.group("project").lower(),
                match.group("client").lower(),
                match.group("page").lower(),
                match.group("module").lower(),
                match.group("case_type").lower(),
                match.group("source").lower(),
            ]
        )
        if candidate_prefix != prefix:
            continue
        highest = max(highest, int(match.group("sequence")))
    return highest + 1 if highest >= 1 else 1


def build_case_metadata(
    *,
    page: str,
    module: str,
    title: str = "",
    description: str = "",
    tags: Any = None,
    project: str = DEFAULT_PROJECT,
    client: str = DEFAULT_CLIENT,
    source_hint: str = "",
    legacy: bool = False,
) -> dict[str, str]:
    page_code = infer_page_code(page, title=title, tags=tags)
    module_code = infer_module_code(page=page, module=module, title=title, tags=tags)
    case_type = infer_case_type(title=title, description=description, tags=tags)
    source = infer_source_code(tags=tags, source_hint=source_hint, legacy=legacy)
    return {
        "project": _to_code(project, fallback=DEFAULT_PROJECT, min_len=2, max_len=10).lower(),
        "client": normalize_client_code(client),
        "page_code": page_code,
        "page_name": PAGE_NAME_MAP.get(page_code.upper(), page or page_code),
        "module_code": module_code,
        "module_name": MODULE_NAME_MAP.get(module_code.upper(), module or module_code),
        "case_type": case_type,
        "case_type_name": CASE_TYPE_NAME_MAP.get(case_type.upper(), case_type),
        "source": source,
        "source_name": SOURCE_NAME_MAP.get(source.upper(), source),
    }
