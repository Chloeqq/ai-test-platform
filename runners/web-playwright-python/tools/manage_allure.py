import argparse
import os
import shutil
import subprocess
from pathlib import Path


def get_runner_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_allure_binary() -> str | None:
    explicit_home = str(os.getenv("ALLURE_HOME", "")).strip()
    candidate_paths = []
    if explicit_home:
        candidate_paths.append(Path(explicit_home) / "bin" / "allure")
    candidate_paths.extend(
        [
            Path("/opt/allure/bin/allure"),
            Path("/usr/local/bin/allure"),
        ]
    )
    for candidate in candidate_paths:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("allure")


def build_default_paths() -> tuple[Path, Path]:
    runner_root = get_runner_root()
    return runner_root / "allure-results", runner_root / "allure-report"


def ensure_allure_available() -> str:
    binary = get_allure_binary()
    if not binary:
        raise RuntimeError("Allure CLI not found in PATH.")
    return binary


def generate_allure_report(results_dir: Path, report_dir: Path) -> subprocess.CompletedProcess[str]:
    binary = ensure_allure_available()
    results_dir = results_dir.expanduser().resolve()
    report_dir = report_dir.expanduser().resolve()
    report_dir.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [binary, "generate", str(results_dir), "-o", str(report_dir), "--clean"],
        text=True,
        capture_output=True,
        check=False,
    )


def open_allure_report(report_dir: Path) -> subprocess.CompletedProcess[str]:
    binary = ensure_allure_available()
    report_dir = report_dir.expanduser().resolve()
    return subprocess.run(
        [binary, "open", str(report_dir)],
        text=True,
        capture_output=True,
        check=False,
    )


def format_info(results_dir: Path, report_dir: Path) -> str:
    binary = get_allure_binary() or "(not found)"
    return "\n".join(
        [
            f"Allure CLI: {binary}",
            f"Results Dir: {results_dir.expanduser().resolve()}",
            f"Report Dir: {report_dir.expanduser().resolve()}",
        ]
    )


def parse_args() -> argparse.Namespace:
    default_results_dir, default_report_dir = build_default_paths()
    parser = argparse.ArgumentParser(description="Manage Allure results for the Python Playwright runner.")
    parser.add_argument(
        "--results-dir",
        default=str(default_results_dir),
        help="Directory containing allure result files.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(default_report_dir),
        help="Directory for generated allure HTML report.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("info", help="Show current Allure CLI and directory settings.")
    subparsers.add_parser("generate", help="Generate an Allure HTML report from allure-results.")
    subparsers.add_parser("open", help="Open an existing Allure HTML report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    report_dir = Path(args.report_dir)

    if args.command == "info":
        print(format_info(results_dir, report_dir))
        return 0

    if args.command == "generate":
        try:
            completed = generate_allure_report(results_dir, report_dir)
        except RuntimeError as exc:
            message = str(exc)
            if "Allure CLI not found" in message:
                print(message)
                return 0
            raise
        print(completed.stdout.strip())
        if completed.returncode != 0:
            print(completed.stderr.strip())
        return completed.returncode

    if args.command == "open":
        try:
            completed = open_allure_report(report_dir)
        except RuntimeError as exc:
            message = str(exc)
            if "Allure CLI not found" in message:
                print(message)
                return 0
            raise
        print(completed.stdout.strip())
        if completed.returncode != 0:
            print(completed.stderr.strip())
        return completed.returncode

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
