import re


VAR_PATTERN = re.compile(r"\{\{(.*?)\}\}")


def resolve_variables(value: str, context: dict):

    if not isinstance(value, str):
        return value

    matches = VAR_PATTERN.findall(value)

    for m in matches:
        key = m.strip()

        if key not in context:
            continue

        value = value.replace(f"{{{{{key}}}}}", str(context[key]))

    return value