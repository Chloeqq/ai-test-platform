from __future__ import annotations

import asyncio
from io import BytesIO
import sys
from typing import Any
from urllib.parse import unquote


class WSGIToASGIAdapter:
    """Minimal WSGI -> ASGI bridge used by local uvicorn runs."""

    def __init__(self, wsgi_app: Any) -> None:
        self._wsgi_app = wsgi_app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": b"Unsupported ASGI scope"})
            return

        body = await self._read_body(receive)
        status_code, headers, response_body = await asyncio.to_thread(self._invoke_wsgi, scope, body)
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": response_body})

    @staticmethod
    async def _read_body(receive: Any) -> bytes:
        chunks: list[bytes] = []
        more_body = True
        while more_body:
            message = await receive()
            if message.get("type") != "http.request":
                continue
            chunk = message.get("body", b"")
            if isinstance(chunk, bytes) and chunk:
                chunks.append(chunk)
            more_body = bool(message.get("more_body", False))
        return b"".join(chunks)

    def _invoke_wsgi(self, scope: dict[str, Any], body: bytes) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
        server = scope.get("server") or ("127.0.0.1", 80)
        client = scope.get("client") or ("127.0.0.1", 0)
        path = unquote(str(scope.get("path", "/") or "/"))
        query_string = scope.get("query_string", b"")
        if isinstance(query_string, bytes):
            query = query_string.decode("latin-1")
        else:
            query = str(query_string or "")
        method = str(scope.get("method", "GET") or "GET").upper()

        environ: dict[str, Any] = {
            "REQUEST_METHOD": method,
            "SCRIPT_NAME": "",
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "SERVER_NAME": str(server[0]),
            "SERVER_PORT": str(server[1]),
            "SERVER_PROTOCOL": "HTTP/1.1",
            "REMOTE_ADDR": str(client[0]),
            "REMOTE_PORT": str(client[1]),
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": str(scope.get("scheme", "http") or "http"),
            "wsgi.input": BytesIO(body),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": True,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
        }

        for header_name, header_value in scope.get("headers", []):
            try:
                key = header_name.decode("latin-1").upper().replace("-", "_")
            except Exception:
                continue
            value = header_value.decode("latin-1") if isinstance(header_value, bytes) else str(header_value)
            if key == "CONTENT_TYPE":
                environ["CONTENT_TYPE"] = value
            elif key == "CONTENT_LENGTH":
                environ["CONTENT_LENGTH"] = value
            else:
                environ[f"HTTP_{key}"] = value

        status_code = 500
        response_headers: list[tuple[bytes, bytes]] = []

        def start_response(status: str, headers: list[tuple[str, str]], _exc_info: Any = None) -> None:
            nonlocal status_code, response_headers
            try:
                status_code = int(str(status).split(" ", 1)[0])
            except Exception:
                status_code = 500
            response_headers = [
                (str(name).encode("latin-1"), str(value).encode("latin-1"))
                for name, value in headers
            ]

        response_chunks: list[bytes] = []
        result = self._wsgi_app(environ, start_response)
        try:
            for chunk in result:
                if isinstance(chunk, bytes):
                    response_chunks.append(chunk)
                else:
                    response_chunks.append(str(chunk).encode("utf-8"))
        finally:
            close = getattr(result, "close", None)
            if callable(close):
                close()

        return status_code, response_headers, b"".join(response_chunks)
