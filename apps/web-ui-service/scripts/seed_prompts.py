"""种子内置 Prompt 模板到 DB。在 make db-bootstrap 时自动调用。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.services.prompt_manager import PromptManager


def main():
    db = SessionLocal()
    try:
        PromptManager.ensure_builtins(db)
        print("prompt_templates: builtin templates seeded")
    finally:
        db.close()


if __name__ == "__main__":
    main()
