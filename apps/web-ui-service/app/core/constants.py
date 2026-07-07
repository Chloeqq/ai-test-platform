"""应用级共享常量 — 单一事实源，避免跨 service 字面量漂移。"""
from __future__ import annotations

# 默认项目代号 — service 在未显式传入 project 时的回退值。
# 历史上在 4 个 service 各自定义同名字面量，现收敛至此。
DEFAULT_PROJECT_CODE = "mall"
