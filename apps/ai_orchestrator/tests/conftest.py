from __future__ import annotations

import sys
from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
ORCHESTRATOR_SRC = TESTS_ROOT.parents[1] / "src"


def _clear_conflicting_modules() -> None:
    for module_name in ("app", "orchestrator_service"):
        sys.modules.pop(module_name, None)


def _ensure_sys_path() -> None:
    entry = str(ORCHESTRATOR_SRC)
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)


_clear_conflicting_modules()
_ensure_sys_path()
