import pytest

from runner.test_case_loader import load_ai_generated_test_cases
from runner.yaml_executor import YamlExecutor


pytestmark = [pytest.mark.e2e, pytest.mark.generated]


test_cases = load_ai_generated_test_cases()


@pytest.mark.parametrize(
    "test_case",
    test_cases,
    ids=[tc["title"] for tc in test_cases],
)
def test_yaml_ai_generated(page, base_url, test_username, test_password, test_case):
    executor = YamlExecutor(
        page=page,
        username=test_username,
        password=test_password,
        base_url=base_url,
    )
    executor.execute(test_case)
