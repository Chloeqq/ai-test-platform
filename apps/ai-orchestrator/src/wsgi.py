"""向后兼容入口：从 app.py 重新导出 FastAPI 应用实例。"""

from app import app  # noqa: E402, F401
