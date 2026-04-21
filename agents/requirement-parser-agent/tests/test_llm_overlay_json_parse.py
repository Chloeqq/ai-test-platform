from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]


def _extract_with_subprocess(raw_payload: object) -> dict[str, object]:
    script = """
import json
from src.agent import RequirementParserAgent

raw = json.loads(__RAW__)
result = RequirementParserAgent._extract_json_object(raw)
print(json.dumps(result, ensure_ascii=False))
"""
    encoded_raw = json.dumps(raw_payload, ensure_ascii=False)
    code = script.replace("__RAW__", repr(encoded_raw))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), str(AGENT_ROOT)])
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(AGENT_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout.strip() or "{}")
    assert isinstance(parsed, dict)
    return parsed


def test_extract_json_object_from_markdown_code_fence() -> None:
    raw = """```json
{"page":"login","test_intents":[{"title":"登录成功","steps":["输入用户名","点击登录"],"expected_result":"登录成功"}]}
```"""
    payload = _extract_with_subprocess(raw)
    assert payload.get("page") == "login"
    assert isinstance(payload.get("test_intents"), list)


def test_extract_json_object_from_segmented_content_parts() -> None:
    raw = [
        {"type": "output_text", "text": "下面是结果："},
        {
            "type": "output_text",
            "text": '{"page":"login","priority":"P1","test_intents":[{"title":"密码错误提示","steps":["输入错误密码"],"expected_result":"提示错误"}]}',
        },
    ]
    payload = _extract_with_subprocess(raw)
    assert payload.get("priority") == "P1"
    assert payload.get("page") == "login"


def test_extract_json_object_from_wrapped_noise_text() -> None:
    raw = """解析结果如下：
{
  "page": "login",
  "test_intents": [
    {"title":"用户名为空提示","steps":["用户名留空","点击登录"],"expected_result":"提示用户名不能为空"}
  ]
}
请按以上为准。"""
    payload = _extract_with_subprocess(raw)
    intents = payload.get("test_intents") if isinstance(payload.get("test_intents"), list) else []
    assert payload.get("page") == "login"
    assert len(intents) == 1
