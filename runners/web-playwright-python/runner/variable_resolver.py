import re


VAR_PATTERN = re.compile(r"\{\{(.*?)\}\}")
FULL_VAR_PATTERN = re.compile(r"^\s*\{\{(.*?)\}\}\s*$")


def _resolve_context_key(context: dict, key: str):
    current = context

    for part in str(key).strip().split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]

    return current, True


def resolve_variables(value: str, context: dict):

    if not isinstance(value, str):
        return value

    full_match = FULL_VAR_PATTERN.match(value)
    if full_match:
        resolved, found = _resolve_context_key(context, full_match.group(1))
        if found:
            return resolved

    matches = VAR_PATTERN.findall(value)

    for m in matches:
        resolved, found = _resolve_context_key(context, m)
        if not found:
            continue

        value = value.replace(f"{{{{{m}}}}}", str(resolved))

    return value
