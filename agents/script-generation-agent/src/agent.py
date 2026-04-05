# mypy: ignore-errors

from __future__ import annotations

import json
import re
from typing import Any

from .schema import GeneratedScript


class ScriptGenerationAgent:
    def generate(
        self,
        *,
        case: dict[str, Any],
        framework: str = "playwright",
        language: str = "python",
    ) -> dict[str, Any]:
        normalized_framework = framework.strip().lower() or "playwright"
        normalized_language = language.strip().lower() or "python"
        if normalized_framework != "playwright":
            raise ValueError("Only playwright framework is supported in current MVP.")
        if normalized_language != "python":
            raise ValueError("Only python language is supported in current MVP.")

        execution = case.get("execution", {}) if isinstance(case, dict) else {}
        case_id = str(case.get("id", "TC-GENERATED-001")).strip() or "TC-GENERATED-001"
        page = str(execution.get("page", case.get("module", "product"))).strip() or "product"
        steps = execution.get("steps", [])
        if not isinstance(steps, list):
            steps = []

        function_name = self._safe_function_name(case_id)
        script_code = self._render_playwright_python(case=case, function_name=function_name)
        output = GeneratedScript(
            version="GeneratedScriptV1",
            framework=normalized_framework,
            language=normalized_language,
            case_id=case_id,
            page=page,
            filename=f"{function_name}.generated.py",
            entrypoint=f"test_{function_name}",
            script_code=script_code,
            metadata={
                "step_count": len(steps),
                "actions": [str((step or {}).get("action", "")).strip() for step in steps],
                "generated_by": "script-generation-agent",
            },
        )
        return output.to_dict()

    @staticmethod
    def _safe_function_name(case_id: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", case_id).strip("_").lower()
        return normalized or "generated_case"

    def _render_playwright_python(self, *, case: dict[str, Any], function_name: str) -> str:
        case_json = json.dumps(case, ensure_ascii=False, indent=2)
        return (
            "import os\n"
            "from pathlib import Path\n"
            "\n"
            "import pytest\n"
            "import yaml\n"
            "from playwright.sync_api import expect\n"
            "\n"
            f"CASE = {case_json}\n"
            "\n"
            "def _load_page_object(page_name: str) -> dict:\n"
            "    repo_root = Path(__file__).resolve().parents[2]\n"
            "    page_object_path = repo_root / 'assets' / 'page-objects' / 'web' / f'{page_name}.page-object.yaml'\n"
            "    return yaml.safe_load(page_object_path.read_text(encoding='utf-8')) or {}\n"
            "\n"
            "def _resolve_locator(page, element: dict):\n"
            "    locator_type = str(element.get('locator_type', '')).strip()\n"
            "    locator_value = element.get('locator_value')\n"
            "    role = element.get('role')\n"
            "    if locator_type == 'placeholder':\n"
            "        return page.get_by_placeholder(locator_value)\n"
            "    if locator_type == 'text':\n"
            "        return page.get_by_text(locator_value)\n"
            "    if locator_type == 'css':\n"
            "        return page.locator(locator_value)\n"
            "    if locator_type == 'role':\n"
            "        return page.get_by_role(role, name=locator_value)\n"
            "    raise ValueError(f'Unsupported locator_type: {locator_type}')\n"
            "\n"
            "def _login(page):\n"
            "    login_url = os.getenv('BASE_URL', 'http://localhost:5173/login#/login')\n"
            "    username = os.getenv('TEST_USERNAME', 'admin')\n"
            "    password = os.getenv('TEST_PASSWORD', 'macro123')\n"
            "    page.goto(login_url, wait_until='domcontentloaded', timeout=60000)\n"
            "    page.get_by_placeholder('请输入用户名').fill(username)\n"
            "    page.get_by_placeholder('请输入密码').fill(password)\n"
            "    page.get_by_role('button', name='登录').click()\n"
            "\n"
            "@pytest.mark.generated\n"
            f"def test_{function_name}(page):\n"
            "    execution = CASE.get('execution', {})\n"
            "    page_name = execution.get('page')\n"
            "    page_object = _load_page_object(page_name)\n"
            "    elements = page_object.get('elements', {})\n"
            "    for step in execution.get('steps', []):\n"
            "        action = step.get('action')\n"
            "        target = step.get('target')\n"
            "        value = step.get('value')\n"
            "        if action == 'login':\n"
            "            _login(page)\n"
            "            continue\n"
            "        if action == 'goto':\n"
            "            page.goto(str(value), wait_until='domcontentloaded', timeout=60000)\n"
            "            continue\n"
            "        if action == 'assert_url':\n"
            "            expect(page).to_have_url(str(value))\n"
            "            continue\n"
            "        if target not in elements:\n"
            "            raise ValueError(f'Missing target in page object: {target}')\n"
            "        locator = _resolve_locator(page, elements[target])\n"
            "        if action == 'click':\n"
            "            locator.click()\n"
            "        elif action == 'fill':\n"
            "            locator.fill(str(value))\n"
            "        elif action == 'wait_for':\n"
            "            expect(locator).to_be_visible(timeout=10000)\n"
            "        elif action == 'assert_visible':\n"
            "            expect(locator).to_be_visible(timeout=10000)\n"
            "        else:\n"
            "            raise ValueError(f'Unsupported action: {action}')\n"
        )
