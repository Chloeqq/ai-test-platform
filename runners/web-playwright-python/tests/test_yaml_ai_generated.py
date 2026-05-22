import pytest

from runner.test_case_loader import load_ai_generated_test_cases
from runner.yaml_executor import YamlExecutor


pytestmark = [pytest.mark.e2e, pytest.mark.generated]


class CaseParam:
    """Keep pytest/Allure parameter display concise while preserving the full payload."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.case_id = str(payload.get("id", "")).strip() or "case"
        self.title = str(payload.get("title", "")).strip()

    def __repr__(self) -> str:
        title_suffix = f", title={self.title!r}" if self.title else ""
        return f"CaseParam(case_id={self.case_id!r}{title_suffix})"


test_cases = [CaseParam(test_case) for test_case in load_ai_generated_test_cases()]


@pytest.mark.parametrize(
    "case_param",
    test_cases,
    ids=[item.case_id or item.title or "case" for item in test_cases],
)
def test_yaml_ai_generated(page, base_url, test_username, test_password, case_param):
    executor = YamlExecutor(
        page=page,
        username=test_username,
        password=test_password,
        base_url=base_url,
    )
    executor.execute(case_param.payload)
