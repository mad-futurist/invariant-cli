from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from invariant_cli.analysis.model import CallResolutionKind
from invariant_cli.matching.static.model import FieldUsage, FunctionFlow, UsageOperation
from invariant_cli.matching.static.python_ast import extract_field_usage, extract_function_flows


@dataclass(frozen=True)
class CallResolution:
    kind: CallResolutionKind
    target: FunctionFlow | None = None
    candidates: tuple[FunctionFlow, ...] = ()


@dataclass(frozen=True)
class ProgramIndex:
    functions: dict[str, FunctionFlow]
    aliases: dict[tuple[str, str], str]

    def resolve(self, call: str, *, caller_module: str | None = None) -> CallResolution:
        if caller_module is not None:
            aliased_name = self.aliases.get((caller_module, call))
            if (
                aliased_name is not None
                and (aliased := self.functions.get(aliased_name)) is not None
            ):
                return CallResolution(
                    CallResolutionKind.EXACT, target=aliased, candidates=(aliased,)
                )

        exact = self.functions.get(call)
        if exact is not None:
            return CallResolution(CallResolutionKind.EXACT, target=exact, candidates=(exact,))

        if caller_module is not None:
            local = self.functions.get(f"{caller_module}.{call}")
            if local is not None:
                return CallResolution(CallResolutionKind.EXACT, target=local, candidates=(local,))

        suffix = call.rsplit(".", 1)[-1]
        matches = tuple(
            flow
            for flow in self.functions.values()
            if flow.function.name.rsplit(".", 1)[-1] == suffix
        )
        if len(matches) == 1:
            return CallResolution(
                CallResolutionKind.HEURISTIC,
                target=matches[0],
                candidates=matches,
            )
        if matches:
            return CallResolution(CallResolutionKind.AMBIGUOUS, candidates=matches)
        return CallResolution(CallResolutionKind.EXTERNAL)

    @classmethod
    def from_flows(
        cls,
        flows: list[FunctionFlow],
        *,
        aliases: dict[tuple[str, str], str] | None = None,
    ) -> ProgramIndex:
        return cls(
            functions={_function_key(flow): flow for flow in flows},
            aliases={} if aliases is None else aliases,
        )


def build_program_index(path: Path) -> ProgramIndex:
    files = python_files(path)
    root = path if path.is_dir() else path.parent
    flows = [
        flow
        for source in files
        for flow in extract_function_flows(source, module=_module_name(source, root))
    ]
    aliases: dict[tuple[str, str], str] = {}
    for source in files:
        module = _module_name(source, root)
        aliases.update(_module_aliases(source, module))
    return ProgramIndex.from_flows(flows, aliases=aliases)


def extract_program_usage(path: Path) -> dict[str, FieldUsage]:
    operations: dict[str, set[UsageOperation]] = {}
    usage_by_file = [extract_field_usage(source) for source in python_files(path)]
    for usage in usage_by_file:
        for identifier, field_usage in usage.items():
            operations.setdefault(identifier, set()).update(field_usage.operations)
    return {
        identifier: FieldUsage(identifier=identifier, operations=set(field_operations))
        for identifier, field_operations in operations.items()
    }


def python_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        candidate
        for candidate in path.rglob("*.py")
        if ".venv" not in candidate.parts and "__pycache__" not in candidate.parts
    )


def _function_key(flow: FunctionFlow) -> str:
    return f"{flow.function.module}.{flow.function.name}"


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def _module_aliases(path: Path, module: str) -> dict[tuple[str, str], str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: dict[str, str] = {}
    aliases: dict[tuple[str, str], str] = {}

    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and statement.module is not None:
            for name in statement.names:
                local = name.asname or name.name
                imported[local] = f"{statement.module}.{name.name}"
                aliases[(module, local)] = imported[local]
        elif isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if not isinstance(target, ast.Name) or not isinstance(statement.value, ast.Call):
                continue
            constructor = _ast_name(statement.value.func)
            class_name = imported.get(constructor or "", constructor)
            if class_name is None:
                continue
            for method in _class_methods(class_name, path.parent):
                aliases[(module, f"{target.id}.{method}")] = f"{class_name}.{method}"
    return aliases


def _class_methods(class_name: str, root: Path) -> tuple[str, ...]:
    module_name, _, short_name = class_name.rpartition(".")
    if not module_name:
        return ()
    module_path = root / Path(*module_name.split(".")).with_suffix(".py")
    if not module_path.is_file():
        return ()
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    return tuple(
        member.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == short_name
        for member in node.body
        if isinstance(member, ast.FunctionDef)
    )


def _ast_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _ast_name(node.value)
        return node.attr if owner is None else f"{owner}.{node.attr}"
    return None
