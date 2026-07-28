"""AST-based EvieAi coding-standard rules."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .model import Violation

MAX_FUNCTION_LINES = 40
MAX_COMPLEXITY = 10
MAX_PARAMETERS = 5
MAX_NESTING = 3

_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)
_LAYER_FORBIDDEN_IMPORTS = {
    "repositories": (
        "app.services",
        "app.routers",
        "app.api",
        "execution_compiler",
        "runner",
    ),
    "policies": (
        "app.models",
        "app.repositories",
        "app.services",
        "app.routers",
        "sqlalchemy",
    ),
    "models": ("app.services", "app.repositories", "app.routers"),
    "schemas": ("app.services", "app.repositories", "app.routers"),
    "services": ("app.routers", "app.api"),
}
_FROZEN_CHAIN_IMPORTS = (
    "behavior_registry",
    "candidate",
    "contractvalidator",
    "execution_compiler",
    "quality_gate",
    "resolve_explicit_step",
    "runner",
    "selected_candidates",
    "structurer",
    "testpointasset",
    "test_point_asset",
)


@dataclass(frozen=True, slots=True)
class _FileContext:
    root: Path
    path: Path
    relative_path: str
    layer: str
    datetime_classes: frozenset[str]
    datetime_modules: frozenset[str]


def scan_ast_rules(root: Path, files: list[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in files:
        violations.extend(_scan_file(root, path))
    return sorted(violations)


def _scan_file(root: Path, path: Path) -> list[Violation]:
    relative_path = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
    datetime_classes, datetime_modules = _datetime_aliases(tree)
    context = _FileContext(
        root=root,
        path=path,
        relative_path=relative_path,
        layer=_layer_for_path(relative_path),
        datetime_classes=frozenset(datetime_classes),
        datetime_modules=frozenset(datetime_modules),
    )
    visitor = _RuleVisitor(context)
    visitor.visit(tree)
    visitor.check_imports(tree)
    return visitor.violations


class _RuleVisitor(ast.NodeVisitor):
    def __init__(self, context: _FileContext) -> None:
        self.context = context
        self.violations: list[Violation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.context.layer == "services" and _is_direct_clock_call(
            node,
            self.context,
        ):
            self._add(
                "EQA001",
                node,
                "Service calls datetime.now()/utcnow() directly",
                "Inject and use the repository clock/provider.",
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        literal = _status_magic_literal(node)
        if literal is not None:
            self._add_status_magic(node, literal)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        literal = _assigned_status_magic(node.targets, node.value)
        if literal is not None:
            self._add_status_magic(node, literal)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        literal = _assigned_status_magic([node.target], node.value)
        if literal is not None:
            self._add_status_magic(node, literal)
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if _is_status_name(node.arg) and _string_literal(node.value) is not None:
            self._add_status_magic(node, _string_literal(node.value) or "")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if _is_error_code_magic(node, self.context.relative_path):
            self._add(
                "EQA007",
                node,
                f"error code uses magic string {node.value!r}",
                "Use the centralized EvieAi error-code definition.",
            )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            if not _annotation_has_any(statement.annotation):
                continue
            self._add(
                "EQA008",
                statement,
                "core value-object field uses Any",
                "Replace Any with an explicit domain type.",
                symbol=node.name,
            )
        self.generic_visit(node)

    def check_imports(self, tree: ast.Module) -> None:
        for module, line in _imports(tree):
            self._check_layer_import(module, line)
            self._check_frozen_chain_import(module, line)

    def _check_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self._check_function_size(node)
        self._check_function_parameters(node)
        self._check_function_complexity(node)
        self._check_function_nesting(node)
        self._check_any_signature(node)

    def _check_function_size(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length <= MAX_FUNCTION_LINES:
            return
        self._add(
            "EQA002",
            node,
            f"{node.name} has {length} lines; maximum is {MAX_FUNCTION_LINES}",
            "Split the function into single-purpose typed units.",
            symbol=node.name,
        )

    def _check_function_parameters(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        parameters = _business_parameters(node)
        if len(parameters) <= MAX_PARAMETERS:
            return
        self._add(
            "EQA003",
            node,
            f"{node.name} has {len(parameters)} parameters; maximum is "
            f"{MAX_PARAMETERS}",
            "Introduce a typed command, context, or configuration object.",
            symbol=node.name,
        )

    def _check_function_complexity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        score = _complexity(node)
        if score <= MAX_COMPLEXITY:
            return
        self._add(
            "EQA004",
            node,
            f"{node.name} complexity is {score}; maximum is {MAX_COMPLEXITY}",
            "Extract explicit policies or smaller branch-specific functions.",
            symbol=node.name,
        )

    def _check_function_nesting(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        depth = _max_nesting(node)
        if depth <= MAX_NESTING:
            return
        self._add(
            "EQA005",
            node,
            f"{node.name} nesting is {depth}; maximum is {MAX_NESTING}",
            "Use guard clauses and extract nested control flow.",
            symbol=node.name,
        )

    def _check_any_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        annotations = [node.returns]
        annotations.extend(arg.annotation for arg in _business_parameters(node))
        if not any(_annotation_has_any(annotation) for annotation in annotations):
            return
        self._add(
            "EQA008",
            node,
            f"{node.name} uses Any in a core signature",
            "Replace Any with explicit input and output domain types.",
            symbol=node.name,
        )

    def _check_layer_import(self, module: str, line: int) -> None:
        forbidden = _LAYER_FORBIDDEN_IMPORTS.get(self.context.layer, ())
        if not any(_module_matches(module, prefix) for prefix in forbidden):
            return
        self._add_at_line(
            "EQA009",
            line,
            f"{self.context.layer} imports forbidden dependency {module!r}",
            "Depend only on the approved lower layer or a public interface.",
            symbol=module,
        )

    def _check_frozen_chain_import(self, module: str, line: int) -> None:
        if not _is_evie_ai_production_path(self.context.relative_path):
            return
        if not _matches_frozen_chain_module(module):
            return
        self._add_at_line(
            "EQA010",
            line,
            f"EvieAi imports frozen generation/execution dependency {module!r}",
            "Remove the dependency and preserve the EvieAi domain boundary.",
            symbol=module,
        )

    def _add_status_magic(self, node: ast.AST, literal: str) -> None:
        self._add(
            "EQA006",
            node,
            f"status or role uses magic string {literal!r}",
            "Use an authoritative Enum or centralized constant.",
        )

    def _add(
        self,
        rule: str,
        node: ast.AST,
        message: str,
        fix: str,
        *,
        symbol: str = "",
    ) -> None:
        self._add_at_line(
            rule,
            getattr(node, "lineno", 0),
            message,
            fix,
            symbol=symbol,
        )

    def _add_at_line(
        self,
        rule: str,
        line: int,
        message: str,
        fix: str,
        *,
        symbol: str = "",
    ) -> None:
        self.violations.append(
            Violation(
                rule=rule,
                path=self.context.relative_path,
                line=line,
                message=message,
                fix=fix,
                symbol=symbol,
            )
        )


def _business_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg]:
    parameters = [
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    if node.args.vararg is not None:
        parameters.append(node.args.vararg)
    if node.args.kwarg is not None:
        parameters.append(node.args.kwarg)
    return [item for item in parameters if item.arg not in {"self", "cls"}]


def _complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    visitor = _ComplexityVisitor(node)
    visitor.visit(node)
    return visitor.score


class _ComplexityVisitor(ast.NodeVisitor):
    def __init__(self, root: ast.AST) -> None:
        self.root = root
        self.score = 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.score += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.score += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.score += max(0, len(node.cases) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.score += 1 + len(node.ifs)
        self.generic_visit(node)


def _max_nesting(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return max(
        (_nested_depth(child, 0) for child in ast.iter_child_nodes(node)),
        default=0,
    )


def _nested_depth(node: ast.AST, depth: int) -> int:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return depth
    next_depth = depth + 1 if isinstance(node, _NESTING_NODES) else depth
    child_depths = (
        _nested_depth(child, next_depth) for child in ast.iter_child_nodes(node)
    )
    return max((next_depth, *child_depths))


def _annotation_has_any(annotation: ast.AST | None) -> bool:
    if annotation is None:
        return False
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id == "Any":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "Any":
            return True
    return False


def _datetime_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    classes: set[str] = set()
    modules: set[str] = set()
    for node in tree.body:
        classes.update(_datetime_class_aliases(node))
        modules.update(_datetime_module_aliases(node))
    return classes, modules


def _datetime_class_aliases(node: ast.stmt) -> set[str]:
    if not isinstance(node, ast.ImportFrom) or node.module != "datetime":
        return set()
    return {
        alias.asname or alias.name for alias in node.names if alias.name == "datetime"
    }


def _datetime_module_aliases(node: ast.stmt) -> set[str]:
    if not isinstance(node, ast.Import):
        return set()
    return {
        alias.asname or alias.name for alias in node.names if alias.name == "datetime"
    }


def _is_direct_clock_call(node: ast.Call, context: _FileContext) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in {"now", "utcnow"}:
        return False
    owner = node.func.value
    if isinstance(owner, ast.Name):
        return owner.id in context.datetime_classes
    if not isinstance(owner, ast.Attribute) or owner.attr != "datetime":
        return False
    return (
        isinstance(owner.value, ast.Name) and owner.value.id in context.datetime_modules
    )


def _status_magic_literal(node: ast.Compare) -> str | None:
    expressions = (node.left, *node.comparators)
    strings = _compared_strings(expressions)
    if not strings:
        return None
    names = _compared_names(expressions)
    if any(name.endswith(("status", "state", "role")) for name in names):
        return strings[0]
    return None


def _assigned_status_magic(
    targets: list[ast.expr],
    value: ast.expr | None,
) -> str | None:
    literal = _string_literal(value)
    if literal is None:
        return None
    if any(_target_has_status_name(target) for target in targets):
        return literal
    return None


def _target_has_status_name(target: ast.expr) -> bool:
    for child in ast.walk(target):
        if isinstance(child, ast.Name) and _is_status_name(child.id):
            return True
        if isinstance(child, ast.Attribute) and _is_status_name(child.attr):
            return True
        if isinstance(child, ast.Constant) and _is_status_name(child.value):
            return True
    return False


def _is_status_name(value: object) -> bool:
    return isinstance(value, str) and value.endswith(("status", "state", "role"))


def _string_literal(value: ast.expr | None) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _compared_strings(expressions: tuple[ast.expr, ...]) -> list[str]:
    return [
        expression.value
        for expression in expressions
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str)
    ]


def _compared_names(expressions: tuple[ast.expr, ...]) -> set[str]:
    names: set[str] = set()
    for expression in expressions:
        for child in ast.walk(expression):
            if isinstance(child, ast.Attribute):
                names.add(child.attr)
            if isinstance(child, ast.Name):
                names.add(child.id)
    return names


def _is_error_code_magic(node: ast.Constant, relative_path: str) -> bool:
    if not _is_evie_ai_production_path(relative_path):
        return False
    if not isinstance(node.value, str) or not node.value.startswith("EVIE_"):
        return False
    authoritative = {
        "apps/web-ui-service/app/errors/evie_ai.py",
        "apps/web-ui-service/app/constants/evie_ai.py",
    }
    return relative_path not in authoritative


def _imports(tree: ast.Module) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.lineno))
    return imports


def _layer_for_path(relative_path: str) -> str:
    for layer in _LAYER_FORBIDDEN_IMPORTS:
        if f"/{layer}/" in f"/{relative_path}/":
            return layer
    return ""


def _module_matches(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def _is_evie_ai_production_path(relative_path: str) -> bool:
    return relative_path.startswith("apps/web-ui-service/app/")


def _matches_frozen_chain_module(module: str) -> bool:
    segments = module.lower().split(".")
    return any(
        _segment_matches_frozen_token(segment, token)
        for segment in segments
        for token in _FROZEN_CHAIN_IMPORTS
    )


def _segment_matches_frozen_token(segment: str, token: str) -> bool:
    return (
        segment == token
        or segment.startswith(f"{token}_")
        or segment.endswith(f"_{token}")
    )
