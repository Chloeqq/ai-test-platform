from .schema import TestCase


def evaluate_testcase_structure(test_case: dict) -> tuple[bool, list[str]]:
    errors = []

    try:
        TestCase(**test_case)
    except Exception as e:
        errors.append(str(e))

    return len(errors) == 0, errors