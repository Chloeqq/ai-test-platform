import pytest
from runner.test_case_loader import load_expanded_test_cases
from runner.yaml_executor import YamlExecutor


pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


test_cases = load_expanded_test_cases("smoke")


@pytest.mark.parametrize(
    "test_case",
    test_cases,
    ids=[tc.get("id") or tc.get("title") or "case" for tc in test_cases],
)
def test_yaml_smoke(page, base_url, test_username, test_password, test_case):

    executor = YamlExecutor(
        page=page,
        username=test_username,
        password=test_password,
        base_url=base_url,
    )

    executor.execute(test_case)
