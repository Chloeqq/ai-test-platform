import argparse
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


def check_base_url_reachable(base_url: str, *, timeout: float = 3.0) -> None:
    try:
        with urlopen(base_url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                raise RuntimeError(f"BASE_URL returned HTTP {status}: {base_url}")
    except URLError as exc:
        host = urlsplit(base_url).hostname or "unknown-host"
        port = urlsplit(base_url).port or ("443" if base_url.startswith("https://") else "80")
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(
            f"BASE_URL is unreachable: {base_url} (host={host}, port={port}, reason={reason})"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether the configured BASE_URL is reachable before running E2E tests.")
    parser.add_argument("--base-url", required=True, help="Target BASE_URL to probe.")
    parser.add_argument("--timeout", type=float, default=3.0, help="Probe timeout in seconds.")
    args = parser.parse_args()

    check_base_url_reachable(args.base_url, timeout=args.timeout)
    print(f"BASE_URL reachable: {args.base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
