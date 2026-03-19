from runner.variable_resolver import resolve_variables


def fill_action(page, locator, step, context, **kwargs):

    value = step.get("value")

    if value is None:
        raise ValueError("fill action requires a value")

    value = resolve_variables(value, context)

    locator.fill(value)
