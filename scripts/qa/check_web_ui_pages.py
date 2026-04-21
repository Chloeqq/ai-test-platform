from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Sequence

from playwright.sync_api import sync_playwright


@dataclass
class PageCheckResult:
    path: str
    page_errors: list[str] = field(default_factory=list)
    dialogs: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.page_errors and not self.dialogs and not self.console_errors


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check core web-ui pages for runtime errors.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8013", help="Web UI base URL")
    parser.add_argument("--auth-username", default=os.environ.get("TEST_USERNAME", "admin"), help="Username for authenticated smoke checks")
    parser.add_argument("--auth-password", default=os.environ.get("TEST_PASSWORD", ""), help="Password for authenticated smoke checks")
    return parser.parse_args(argv)


def check_page(page, base_url: str, path: str) -> PageCheckResult:
    result = PageCheckResult(path=path)

    def on_page_error(error: BaseException) -> None:
        result.page_errors.append(repr(error))

    def on_dialog(dialog) -> None:  # type: ignore[no-untyped-def]
        result.dialogs.append(dialog.message)
        dialog.dismiss()

    def on_console(message) -> None:  # type: ignore[no-untyped-def]
        if message.type != "error":
            return
        text = str(message.text or "").strip()
        if not text:
            return
        result.console_errors.append(text)

    page.on("pageerror", on_page_error)
    page.on("dialog", on_dialog)
    page.on("console", on_console)
    page.goto(f"{base_url.rstrip('/')}{path}", wait_until="networkidle", timeout=30000)
    return result


def fetch_access_token(base_url: str, username: str, password: str) -> str:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": username, "password": password}).encode("utf-8"),
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload.get("access_token") or "").strip()


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    paths = [
        "/cases?sort_dir=desc&sort_key=status",
        "/ai-generation",
        "/assets/page-objects",
        "/assets/page-objects/recorder",
        "/execution/workbench?project=atp",
    ]
    failures: list[PageCheckResult] = []
    access_token = fetch_access_token(args.base_url, args.auth_username, args.auth_password)
    if not access_token:
        print("[check-web-ui-pages] failed to obtain access token for authenticated checks", file=sys.stderr)
        return 1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            scenarios = [
                ("anonymous", None),
                ("authenticated", access_token),
            ]
            for label, token in scenarios:
                context = browser.new_context()
                if token:
                    context.add_init_script(
                        script=(
                            "window.localStorage.setItem("
                            "\"ai_test_platform.access_token\", "
                            f"{json.dumps(token)}"
                            ");"
                        )
                    )
                try:
                    for path in paths:
                        page = context.new_page()
                        try:
                            result = check_page(page, args.base_url, path)
                            print(f"[check-web-ui-pages] {label} {path} :: {'PASS' if result.ok else 'FAIL'}")
                            if result.page_errors:
                                print(f"  page_errors={result.page_errors}")
                            if result.dialogs:
                                print(f"  dialogs={result.dialogs}")
                            if result.console_errors:
                                print(f"  console_errors={result.console_errors}")
                            if not result.ok:
                                failures.append(result)
                        finally:
                            page.close()
                finally:
                    context.close()
        finally:
            browser.close()

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
