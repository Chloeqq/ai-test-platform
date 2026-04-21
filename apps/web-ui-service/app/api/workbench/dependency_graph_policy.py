from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]


ARCHITECTURE_REGISTRY_PATH = Path(__file__).with_name("architecture_registry.yaml")


@dataclass(frozen=True)
class DependencyGraphViolation:
    message: str


def load_architecture_registry(path: Path = ARCHITECTURE_REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    if yaml is not None:
        try:
            payload = yaml.safe_load(text)  # type: ignore[union-attr]
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


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
                continue
            if neighbor in on_stack:
                start = stack.index(neighbor)
                cycles.append(stack[start:] + [neighbor])
        stack.pop()
        on_stack.remove(node)

    for node in sorted(graph):
        if node not in visited:
            visit(node)
    return cycles


def validate_dependency_graph(modules: dict[str, list[str]], *, forbidden_edges: set[tuple[str, str]] | None = None) -> None:
    graph = {module: {dep for dep in deps if dep} for module, deps in modules.items()}
    cycles = _detect_cycles(graph)
    if cycles:
        cycle_text = "; ".join(" -> ".join(cycle) for cycle in cycles)
        raise ValueError(f"Circular dependency detected: {cycle_text}")

    violations: list[str] = []
    forbidden = forbidden_edges or set()
    for source, deps in graph.items():
        for dep in sorted(deps):
            if (source, dep) in forbidden:
                violations.append(f"{source} -> {dep}")
            if source.startswith("app.services") and dep.startswith("app.routers"):
                violations.append(f"{source} -> {dep}")

    if violations:
        unique = sorted(dict.fromkeys(violations))
        raise ValueError("Dependency policy violation(s): " + "; ".join(unique))
