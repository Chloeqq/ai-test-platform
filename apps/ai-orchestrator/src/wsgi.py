"""向后兼容入口：从 main.py 重新导出 FastAPI 应用实例。"""
from main import app  # noqa: E402, F401
