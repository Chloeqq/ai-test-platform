import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
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


def _read_latest_result(results_dir: Path) -> dict:
    candidates = sorted(
        results_dir.glob("*-result.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _labels_by_name(result: dict) -> dict[str, str]:
    labels = result.get("labels")
    output: dict[str, str] = {}
    if not isinstance(labels, list):
        return output
    for item in labels:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        value = str(item.get("value", "")).strip()
        if name and value and name not in output:
            output[name] = value
    return output


def _build_report_identity(result: dict) -> dict[str, str]:
    labels = _labels_by_name(result)
    case_title = labels.get("case_title") or str(result.get("name", "")).strip() or "自动化测试"
    case_id = labels.get("case_id") or labels.get("story") or ""
    page = labels.get("page") or labels.get("feature") or os.getenv("TEST_PAGE", "").strip()
    case_version = labels.get("case_version") or os.getenv("TEST_CASE_VERSION", "").strip() or "v1"
    if case_version and not case_version.lower().startswith("v"):
        case_version = f"v{case_version}"
    run_id = os.getenv("WORKBENCH_RUN_ID", "").strip()
    run_token = f"run-{run_id[:8]}" if run_id else "r1"
    started_ms = int(result.get("start", 0) or 0)
    if started_ms > 0:
        report_date = datetime.fromtimestamp(started_ms / 1000, tz=timezone.utc).date().isoformat()
    else:
        report_date = datetime.now(timezone.utc).date().isoformat()
    version_seed = case_id or page or "allure"
    compact_seed = "".join(char if char.isalnum() else "-" for char in version_seed).strip("-") or "allure"
    display_version = f"{compact_seed}-{case_version}.{run_token}" if case_id else f"{compact_seed}-{report_date}-{run_token}"
    return {
        "display_version": display_version,
        "report_name": f"{case_title} - 回归执行报告 ({display_version})",
        "case_title": case_title,
        "case_id": case_id,
        "page": page,
        "case_version": case_version,
        "run_id": run_id,
    }


def _properties_escape(value: str) -> str:
    output = []
    for char in str(value or ""):
        codepoint = ord(char)
        if char == "\\":
            output.append("\\\\")
        elif char == "\n":
            output.append("\\n")
        elif char == "\r":
            output.append("\\r")
        elif char == "\t":
            output.append("\\t")
        elif codepoint > 127:
            output.append(f"\\u{codepoint:04x}")
        else:
            output.append(char)
    return "".join(output)


def write_allure_metadata(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    result = _read_latest_result(results_dir)
    labels = _labels_by_name(result)
    identity = _build_report_identity(result)
    base_url = labels.get("base_url") or os.getenv("BASE_URL", "")
    project = labels.get("project") or os.getenv("TEST_PROJECT", "").strip() or "mall"
    run_source = labels.get("run_source") or os.getenv("RUN_SOURCE", "manual")
    run_mode = labels.get("run_mode") or os.getenv("RUN_MODE", "unspecified")
    browser = os.getenv("BROWSER", "chromium")
    environment = os.getenv("APP_ENV", "").strip() or os.getenv("TEST_ENV", "").strip() or "local-demo"
    platform_url = os.getenv("PLATFORM_BASE_URL", "http://127.0.0.1:8013")

    environment_lines = [
        ("Project", project),
        ("Environment", environment),
        ("Base_URL", base_url),
        ("Browser", browser),
        ("Runner", "pytest + playwright"),
        ("Run_Source", run_source),
        ("Run_Mode", run_mode),
        ("Case_ID", identity["case_id"]),
        ("Case_Title", identity["case_title"]),
        ("Page", identity["page"]),
        ("Run_ID", identity["run_id"]),
        ("Report_Version", identity["display_version"]),
    ]
    (results_dir / "environment.properties").write_text(
        "\n".join(f"{key}={_properties_escape(value)}" for key, value in environment_lines if str(value).strip()) + "\n",
        encoding="utf-8",
    )
    (results_dir / "executor.json").write_text(
        json.dumps(
            {
                "name": "AI 质量保障平台",
                "type": "pytest-playwright",
                "url": platform_url,
                "buildName": identity["display_version"],
                "buildUrl": platform_url.rstrip("/") + "/react/execution/results/allure",
                "reportName": identity["report_name"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (results_dir / "report-name.txt").write_text(identity["report_name"] + "\n", encoding="utf-8")
    write_categories_json(results_dir)


def write_categories_json(results_dir: Path) -> None:
    categories = [
        {
            "name": "环境/页面不可达",
            "matchedStatuses": ["broken", "failed"],
            "messageRegex": ".*(E2E preflight|ERR_CONNECTION|net::ERR|Page\\.goto|Target page|Timeout.*goto|base_url).*",
        },
        {
            "name": "元素定位失败",
            "matchedStatuses": ["broken", "failed"],
            "messageRegex": ".*(locator|strict mode violation|waiting for.*locator|requires compiled selector|not found|元素|定位).*",
        },
        {
            "name": "断言失败",
            "matchedStatuses": ["failed"],
            "messageRegex": ".*(AssertionError|assert|断言|expected).*",
        },
        {
            "name": "用例数据/前置条件失败",
            "matchedStatuses": ["broken", "failed"],
            "messageRegex": ".*(TEST_USERNAME|TEST_PASSWORD|Missing execution|precondition|前置条件|用例数据).*",
        },
        {
            "name": "执行器异常",
            "matchedStatuses": ["broken"],
            "messageRegex": ".*(Unsupported action|runner|YamlExecutor|执行器|Traceback).*",
        },
    ]
    (results_dir / "categories.json").write_text(
        json.dumps(categories, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def rewrite_report_summary(report_dir: Path, *, report_name: str) -> None:
    summary_path = report_dir / "widgets" / "summary.json"
    if not summary_path.exists():
        return
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    if not isinstance(payload, dict):
        payload = {}
    payload["reportName"] = report_name
    summary_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def generate_allure_report(results_dir: Path, report_dir: Path) -> subprocess.CompletedProcess[str]:
    binary = ensure_allure_available()
    results_dir = results_dir.expanduser().resolve()
    report_dir = report_dir.expanduser().resolve()
    identity = _build_report_identity(_read_latest_result(results_dir))
    write_allure_metadata(results_dir)
    report_dir.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [binary, "generate", str(results_dir), "-o", str(report_dir), "--clean"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        rewrite_report_summary(report_dir, report_name=identity["report_name"])
    return completed


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
