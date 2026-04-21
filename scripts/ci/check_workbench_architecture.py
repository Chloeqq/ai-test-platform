#!/usr/bin/env python3
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
import importlib
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"
WEB_UI_APP_ROOT = APPS_ROOT / "web-ui-service"

if str(WEB_UI_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_UI_APP_ROOT))

from app.api.workbench.dependency_graph_policy import load_architecture_registry, validate_dependency_graph  # noqa: E402


def _iter_python_files() -> list[Path]:
    return sorted(path for path in APPS_ROOT.rglob("*.py") if path.is_file())


def _check_forbidden_imports() -> list[str]:
    violations: list[str] = []
    forbidden_patterns = [
        "from shared_backend import *",
        "from shared_backend.schemas import *",
    ]
    for path in _iter_python_files():
        text = path.read_text(encoding="utf-8")
        if "apps.shared_backend" in text:
            violations.append(f"{path}: contains forbidden import path `apps.shared_backend`")
        for pattern in forbidden_patterns:
            if pattern in text:
                violations.append(f"{path}: contains forbidden star import `{pattern}`")
    return violations


def _check_test_cases_route_duplication() -> list[str]:
    router_files = sorted((APPS_ROOT / "web-ui-service" / "app" / "routers").glob("*.py"))
    duplicates: list[str] = []
    deprecated_router = APPS_ROOT / "web-ui-service" / "app" / "routers" / "test_cases_paginated.py"
    if deprecated_router.exists():
        duplicates.append(f"{deprecated_router}: duplicate router file must be removed")
    active_files: list[Path] = []
    for path in router_files:
        text = path.read_text(encoding="utf-8")
        if 'APIRouter(prefix="/api/test-cases"' in text and "/_deprecated/" not in text:
            active_files.append(path)
    if len(active_files) > 1:
        duplicates.append(
            "multiple active `/api/test-cases` routers detected: "
            + ", ".join(str(path.relative_to(REPO_ROOT)) for path in active_files)
        )
    return duplicates


def _check_webui_compiler_wrapper() -> list[str]:
    path = APPS_ROOT / "web-ui-service" / "app" / "services" / "workbench_generation_compiler" / "execution_compiler.py"
    if not path.exists():
        return [f"{path}: missing compiler wrapper"]
    text = path.read_text(encoding="utf-8")
    if "from shared_backend.execution_compiler import *" not in text:
        return [f"{path}: must forward to shared_backend.execution_compiler"]
    return []


def _check_shared_backend_shadow_package() -> list[str]:
    shadow_root = APPS_ROOT / "shared_backend"
    if not shadow_root.exists():
        return []
    violations: list[str] = []
    for path in sorted(shadow_root.glob("*.py")):
        if path.name == "__init__.py":
            continue
        violations.append(f"{path}: shadow package must not contain implementation module")
    return violations


def _check_shared_backend_resolution() -> list[str]:
    violations: list[str] = []
    root = str(REPO_ROOT)
    apps = str(APPS_ROOT)
    original = list(sys.path)
    try:
        for order in ([root, apps], [apps, root]):
            sys.path = order + [item for item in original if item not in order]
            for key in list(sys.modules):
                if key == "shared_backend" or key.startswith("shared_backend."):
                    del sys.modules[key]
            module = importlib.import_module("shared_backend")
            module_path = [str(item) for item in getattr(module, "__path__", [])]
            expected = str(REPO_ROOT / "shared_backend")
            if expected not in module_path:
                violations.append(
                    "shared_backend resolution drift detected: "
                    f"order={order}, module_file={getattr(module, '__file__', '')}, module_path={module_path}"
                )
    finally:
        sys.path = original
    return violations


def _check_architecture_registry() -> list[str]:
    path = WEB_UI_APP_ROOT / "app" / "api" / "workbench" / "architecture_registry.yaml"
    if not path.exists():
        return [f"{path}: missing architecture registry"]
    payload = load_architecture_registry(path)
    chain = (((payload.get("architecture") or {}).get("source_of_truth_chain")) if isinstance(payload, dict) else None)
    if chain != ["router", "facade", "service", "store", "filesystem"]:
        return [f"{path}: registry missing source-of-truth chain"]
    return []


def _is_dependency_scope(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    if not rel.parts:
        return False
    if rel.parts[0] == "shared_backend":
        return rel.name in {"__init__.py", "case_ids.py", "execution_compiler.py", "mapping_engine.py"}
    if rel.parts[:3] != ("apps", "web-ui-service", "app"):
        return False
    if len(rel.parts) < 5:
        return False
    if rel.parts[3] == "routers":
        return rel.name.startswith("workbench_") or rel.name == "legacy_workbench.py"
    if rel.parts[3] == "api" and rel.parts[4] == "legacy_workbench":
        return rel.name.endswith(".py")
    if rel.parts[3] != "services":
        return False
    if rel.parts[4] == "workbench_generation_api":
        return True
    return rel.name in {
        "workbench_generation_service.py",
        "workbench_runtime_service.py",
        "workbench_analysis_service.py",
        "workbench_gate_service.py",
        "workbench_asset_service.py",
        "workbench_reporting_service.py",
        "workbench_state_store.py",
        "workbench_orchestrator_service.py",
        "workbench_review_service.py",
        "workbench_history_service.py",
        "workbench_case_consistency_service.py",
        "workbench_project_service.py",
        "workbench_task_service.py",
        "test_case_service.py",
        "test_point_service.py",
    }


def _iter_dependency_files() -> list[Path]:
    candidates: list[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        try:
            if _is_dependency_scope(path):
                candidates.append(path)
        except ValueError:
            continue
    return sorted(dict.fromkeys(candidates))


def _module_name_for_path(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    parts = list(rel.parts)
    if parts[:3] == ["apps", "web-ui-service", "app"]:
        module_parts = ["app"] + parts[3:]
    elif parts and parts[0] == "shared_backend":
        module_parts = ["shared_backend"] + parts[1:]
    else:
        return ""
    if module_parts[-1] == "__init__.py":
        module_parts = module_parts[:-1]
    else:
        module_parts[-1] = module_parts[-1][:-3]
    return ".".join(module_parts)


def _resolve_relative_module(current_module: str, module: str | None, level: int) -> str:
    if level <= 0:
        return module or ""
    current_parts = current_module.split(".")
    base_parts = current_parts[:-level]
    if module:
        base_parts.extend(module.split("."))
    return ".".join(part for part in base_parts if part)


def _build_dependency_graph() -> tuple[dict[str, set[str]], dict[str, Path]]:
    module_paths: dict[str, Path] = {}
    for path in _iter_dependency_files():
        module_name = _module_name_for_path(path)
        if module_name:
            module_paths[module_name] = path

    graph: dict[str, set[str]] = {module: set() for module in module_paths}
    for module_name, path in module_paths.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    candidate = alias.name.strip()
                    if candidate in module_paths:
                        graph[module_name].add(candidate)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_relative_module(module_name, node.module, int(node.level or 0))
                if not base:
                    continue
                if base in module_paths:
                    graph[module_name].add(base)
                for alias in node.names:
                    candidate = f"{base}.{alias.name}".rstrip(".")
                    if candidate in module_paths:
                        graph[module_name].add(candidate)
    return graph, module_paths


def _detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    visited: set[str] = set()
    on_stack: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        visited.add(node)
        on_stack.add(node)
        stack.append(node)
        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in visited:
                visit(neighbor)
            elif neighbor in on_stack:
                start_index = stack.index(neighbor)
                cycles.append(stack[start_index:] + [neighbor])
        stack.pop()
        on_stack.remove(node)

    for node in sorted(graph):
        if node not in visited:
            visit(node)
    return cycles


def _check_dependency_graph() -> list[str]:
    graph, _module_paths = _build_dependency_graph()
    violations: list[str] = []
    print("MODULE DEPENDENCY GRAPH")
    for module in sorted(graph):
        neighbors = sorted(graph.get(module, set()))
        if not neighbors:
            print(f"{module} -> (no local imports)")
            continue
        for neighbor in neighbors:
            print(f"{module} -> {neighbor}")
    try:
        validate_dependency_graph({module: sorted(neighbors) for module, neighbors in graph.items()})
    except ValueError as exc:
        violations.append(str(exc))
    cycles = _detect_cycles(graph)
    if cycles:
        for cycle in cycles:
            violations.append("circular dependency detected: " + " -> ".join(cycle))
    else:
        print("No module cycles detected.")
    return violations


def _check_generation_surface_contracts() -> list[str]:
    violations: list[str] = []
    surface_files = [
        APPS_ROOT / "web-ui-service" / "app" / "routers" / "workbench_generation.py",
        APPS_ROOT / "web-ui-service" / "app" / "services" / "workbench_generation_api",
    ]
    forbidden_patterns = [
        "getattr(legacy_workbench",
        "from app.routers import legacy_workbench",
        "import legacy_workbench",
        "legacy_workbench.",
        "SETTINGS = ",
        "setattr(SETTINGS",
    ]
    for root in surface_files:
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for pattern in forbidden_patterns:
                if pattern in text:
                    violations.append(f"{path}: contains forbidden generation-surface pattern `{pattern}`")
    return violations


def _check_legacy_runtime_facade_wrappers() -> list[str]:
    path = APPS_ROOT / "web-ui-service" / "app" / "services" / "workbench_generation_api" / "legacy_runtime_facade.py"
    if not path.exists():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: failed to parse for wrapper check: {exc}"]

    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        body = [stmt for stmt in node.body if not isinstance(stmt, ast.Expr) or not isinstance(getattr(stmt, "value", None), ast.Constant)]
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        value = body[0].value
        if isinstance(value, ast.Call):
            violations.append(f"{path}: wrapper-only function `{node.name}` must be removed or aliased")
    return violations


def _check_legacy_runtime_facade_alias_only() -> list[str]:
    path = APPS_ROOT / "web-ui-service" / "app" / "services" / "workbench_generation_api" / "legacy_runtime_facade.py"
    if not path.exists():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path}: failed to parse for alias-only check: {exc}"]
    violations: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            violations.append(f"{path}: function `{node.name}` must be replaced by alias/partial")
    return violations


def _check_compat_shim_purity() -> list[str]:
    path = APPS_ROOT / "web-ui-service" / "app" / "api" / "legacy_workbench" / "compat.py"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    forbidden = [
        "if not hasattr(",
        "setattr(",
        "._sync_stage_",
        "fallback",
        "decision",
        "branch",
    ]
    violations: list[str] = []
    for pattern in forbidden:
        if pattern in text:
            violations.append(f"{path}: contains forbidden compat pattern `{pattern}`")
    return violations


def _check_service_settings_globals() -> list[str]:
    violations: list[str] = []
    service_root = APPS_ROOT / "web-ui-service" / "app" / "services"
    for path in sorted(service_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == "SETTINGS" for target in node.targets):
                violations.append(f"{path}: module-level SETTINGS assignment is forbidden")
    return violations


def _check_new_chain_field_leaks() -> list[str]:
    """Prevent any code from writing legacy fields (dependent_elements)."""
    violations: list[str] = []
    write_patterns = {
        '"dependent_elements"': "dependent_elements usage (use involved_elements)",
        "'dependent_elements'": "dependent_elements usage (use involved_elements)",
        "dependent_elements=": "dependent_elements assignment (use involved_elements)",
        "dependent_elements:": "dependent_elements type annotation (use involved_elements)",
    }
    exempt_files = {
        "check_workbench_architecture.py",
    }
    scan_roots = [
        APPS_ROOT / "web-ui-service" / "app" / "services",
        APPS_ROOT / "web-ui-service" / "app" / "core",
        APPS_ROOT / "ai-orchestrator" / "src",
        REPO_ROOT / "agents" / "test-design-agent" / "src",
        REPO_ROOT / "shared_backend",
    ]
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if path.name in exempt_files:
                continue
            if "test" in path.name.lower() or "__pycache__" in str(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for pattern, description in write_patterns.items():
                if pattern in text:
                    violations.append(f"{path}: {description}")
    return violations


def _check_preview_architecture_symbols() -> list[str]:
    forbidden = [
        "Preview" + "TestPoints" + "Service",
        "build_" + "preview_" + "test_points_" + "service",
        "Preview" + "TestPoints" + "UseCase",
        "build_" + "preview_" + "test_points_" + "usecase",
        "build_" + "preview_" + "compiler",
        "build_" + "preview_" + "orchestrator_" + "client",
        "build_" + "preview_" + "test_points_" + "payload",
    ]
    text_suffixes = {".py", ".md", ".sh", ".json", ".yaml", ".yml", ".toml"}
    violations: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in text_suffixes:
            continue
        if any(part in {"actions-runner", ".venv", "node_modules", ".git"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for pattern in forbidden:
            if pattern in text:
                violations.append(f"{path}: contains forbidden preview symbol `{pattern}`")
    return violations


def _extract_route_path(decorator: ast.Call) -> str:
    if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
        return decorator.args[0].value
    for keyword in decorator.keywords:
        if keyword.arg == "path" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return ""


def _check_ui_router_htmlresponse_policy() -> list[str]:
    routers_root = APPS_ROOT / "web-ui-service" / "app" / "routers"
    allowed: dict[str, set[str]] = {
        "ui_operations_pages.py": {"/react", "/react/{subpath:path}"},
    }
    violations: list[str] = []
    for path in sorted(routers_root.glob("ui*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:
            violations.append(f"{path}: failed to parse ui router for HTMLResponse guard: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr not in {"get", "post", "put", "patch", "delete", "api_route"}:
                    continue
                has_html_response = any(
                    keyword.arg == "response_class"
                    and isinstance(keyword.value, ast.Name)
                    and keyword.value.id == "HTMLResponse"
                    for keyword in decorator.keywords
                )
                if not has_html_response:
                    continue
                route_path = _extract_route_path(decorator)
                allowed_paths = allowed.get(path.name, set())
                if route_path not in allowed_paths:
                    violations.append(
                        f"{path}: route `{route_path or '<unknown>'}` uses forbidden HTMLResponse; "
                        "UI routes must redirect to /react/* except React shell."
                    )
    return violations


def _check_react_only_static_assets() -> list[str]:
    templates_dir = APPS_ROOT / "web-ui-service" / "app" / "templates"
    static_dir = APPS_ROOT / "web-ui-service" / "app" / "static"
    violations: list[str] = []

    if templates_dir.exists():
        legacy_templates = sorted(
            path for path in templates_dir.glob("*.html") if path.name != "react_app.html"
        )
        for path in legacy_templates:
            violations.append(f"{path}: legacy template must be removed (React shell only).")

    if static_dir.exists():
        legacy_static_files = sorted(path for path in static_dir.glob("*") if path.is_file())
        for path in legacy_static_files:
            violations.append(f"{path}: legacy static root file must be removed (React bundle only).")

    react_shell = templates_dir / "react_app.html"
    if react_shell.exists():
        text = react_shell.read_text(encoding="utf-8")
        required_assets = ["/static/react/assets/main.css", "/static/react/assets/main.js"]
        for asset in required_assets:
            if asset not in text:
                violations.append(f"{react_shell}: missing required React asset reference `{asset}`")
    return violations


def main() -> int:
    violations: list[str] = []
    violations.extend(_check_forbidden_imports())
    violations.extend(_check_test_cases_route_duplication())
    violations.extend(_check_webui_compiler_wrapper())
    violations.extend(_check_shared_backend_shadow_package())
    violations.extend(_check_shared_backend_resolution())
    violations.extend(_check_architecture_registry())
    violations.extend(_check_dependency_graph())
    violations.extend(_check_generation_surface_contracts())
    violations.extend(_check_legacy_runtime_facade_wrappers())
    violations.extend(_check_legacy_runtime_facade_alias_only())
    violations.extend(_check_compat_shim_purity())
    violations.extend(_check_service_settings_globals())
    violations.extend(_check_new_chain_field_leaks())
    violations.extend(_check_preview_architecture_symbols())
    violations.extend(_check_ui_router_htmlresponse_policy())
    violations.extend(_check_react_only_static_assets())
    if violations:
        print("Workbench architecture guard failed:")
        for item in violations:
            print(f"- {item}")
        return 1
    print("Workbench architecture guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
