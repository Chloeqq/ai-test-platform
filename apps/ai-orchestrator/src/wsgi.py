"""WSGI 部署入口：导出 Flask 应用实例供 gunicorn/uwsgi 加载。"""

from app import create_app  # type: ignore[import-not-found]


app = create_app()
