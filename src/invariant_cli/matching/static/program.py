from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from invariant_cli.matching.static.model import FieldUsage, FunctionFlow, UsageOperation
from invariant_cli.matching.static.python_ast import extract_field_usage, extract_function_flows


@dataclass(frozen=True)
class ProgramIndex:
    functions: dict[str, FunctionFlow]

    def resolve(self, call: str) -> FunctionFlow | None:
        exact = self.functions.get(call)
        if exact is not None:
            return exact

        suffix = call.rsplit(".", 1)[-1]
        matches = {
            _function_key(flow): flow
            for flow in self.functions.values()
            if flow.function.name.rsplit(".", 1)[-1] == suffix
        }
        if len(matches) == 1:
            return next(iter(matches.values()))
        return None

    @classmethod
    def from_flows(cls, flows: list[FunctionFlow]) -> ProgramIndex:
        return cls(functions={_function_key(flow): flow for flow in flows})


def build_program_index(path: Path) -> ProgramIndex:
    files = python_files(path)
    root = path if path.is_dir() else path.parent
    flows = [
        flow
        for source in files
        for flow in extract_function_flows(source, module=_module_name(source, root))
    ]
    return ProgramIndex.from_flows(flows)


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
