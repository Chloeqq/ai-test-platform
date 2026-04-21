#!/usr/bin/env python3
"""Start the in-repo login demo (fixtures/login-demo) and run login validation E2E tests.

Usage (from repo root)::

    .venv/bin/python runners/web-playwright-python/tools/run_login_e2e_demo.py

With extra pytest options::

    .venv/bin/python runners/web-playwright-python/tools/run_login_e2e_demo.py -x --tb=short

Credentials are fixed: demo / demo123 (see fixtures/login-demo/index.html).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


def _main() -> int:
    runner_root = Path(__file__).resolve().parents[1]
    fixture_dir = runner_root / "fixtures" / "login-demo"
    if not fixture_dir.is_dir():
        print(f"missing fixture dir: {fixture_dir}", file=sys.stderr)
        return 2

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(fixture_dir), **kwargs)

        def log_message(self, _format, *_args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}/#/login"
    env = os.environ.copy()
    env["BASE_URL"] = base_url
    env["TEST_USERNAME"] = "demo"
    env["TEST_PASSWORD"] = "demo123"
    sep = os.pathsep
    path_parts = [str(runner_root), str(runner_root / "tools")]
    existing = env.get("PYTHONPATH", "").strip()
    if existing:
        path_parts.append(existing)
    env["PYTHONPATH"] = sep.join(path_parts)

    pytest_extra = [a for a in sys.argv[1:] if a]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(runner_root / "tests" / "test_login_validation_e2e.py"),
        "-m",
        "e2e",
        "-v",
        *pytest_extra,
    ]
    try:
        return subprocess.call(cmd, cwd=str(runner_root), env=env)
    finally:
        server.shutdown()
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(_main())
