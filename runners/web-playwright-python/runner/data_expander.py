from copy import deepcopy


def expand_test_case(test_case: dict) -> list[dict]:
    """
    根据 data 字段展开测试用例
    """

    data = test_case.get("data")

    if not data:
        return [test_case]

    keys = list(data.keys())
    lengths = []

    for key, value in data.items():
        if not isinstance(value, list):
            raise ValueError(f"Test case data field '{key}' must be a list")

        if not value:
            raise ValueError(f"Test case data field '{key}' must not be empty")

        lengths.append(len(value))

    if len(set(lengths)) != 1:
        raise ValueError(
            f"All test case data fields must have the same length, got: {dict(zip(keys, lengths))}"
        )

    cases = []

    for i in range(lengths[0]):
        new_case = deepcopy(test_case)

        new_case["_data"] = {}

        for key in keys:
            new_case["_data"][key] = data[key][i]

        cases.append(new_case)

    return cases
