import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from patch_generator import REPO_ROOT


RUNNER_ROOT = REPO_ROOT / "runners" / "web-playwright-python"


class RerunRunner:
    def __init__(
        self,
        *,
        runner_root: Path = RUNNER_ROOT,
        python_executable: str | None = None,
    ):
        self.runner_root = runner_root
        self.python_executable = python_executable or sys.executable

    def run(self, *, case_path: Path, case_id: str, previous_attempts: int = 0) -> dict[str, Any]:
        env = os.environ.copy()
        env["RUN_MODE"] = "ai"
        env["TEST_CASE_ID"] = case_id
        env["TEST_CASE_PATH"] = str(case_path.resolve())
        env["SELF_HEALING_ATTEMPTS"] = str(previous_attempts + 1)

        existing_pythonpath = env.get("PYTHONPATH", "")
        runner_pythonpath = str(self.runner_root)
        env["PYTHONPATH"] = (
            f"{runner_pythonpath}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else runner_pythonpath
        )

        completed = subprocess.run(
            [self.python_executable, "-m", "pytest", "tests/test_yaml_ai_generated.py", "-q"],
            cwd=self.runner_root,
            env=env,
            text=True,
            capture_output=True,
        )
        return {
            "success": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "command": [self.python_executable, "-m", "pytest", "tests/test_yaml_ai_generated.py", "-q"],
        }
