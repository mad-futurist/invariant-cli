import ast
from pathlib import Path

from invariant_cli.matching.static.model import FieldUsage, UsageOperation


def extract_field_usage(path: Path) -> dict[str, FieldUsage]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

    collector = _UsageCollector()
    collector.visit(tree)

    return {
        identifier: FieldUsage(
            identifier=identifier,
            operations=operations,
        )
        for identifier, operations in collector.operations.items()
    }


class _UsageCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.operations: dict[str, set[UsageOperation]] = {}

    def visit_Subscript(self, node: ast.Subscript) -> None:
        identifier = _string_key(node)

        if identifier is not None:
            if isinstance(node.ctx, ast.Load):
                self._add(identifier, UsageOperation.READ)
            elif isinstance(node.ctx, ast.Store):
                self._add(identifier, UsageOperation.WRITE)

        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Subscript):
            identifier = _string_key(node.target)

            if identifier is not None:
                self._add(identifier, UsageOperation.READ)
                self._add(identifier, UsageOperation.WRITE)

                operation = _operation(node.op)
                if operation is not None:
                    self._add(identifier, operation)

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        operation = _operation(node.op)

        if operation is not None:
            for identifier in _field_identifiers(node):
                self._add(identifier, operation)

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for identifier in _field_identifiers(node):
            self._add(identifier, UsageOperation.COMPARE)

        self.generic_visit(node)

    def _add(self, identifier: str, operation: UsageOperation) -> None:
        self.operations.setdefault(identifier, set()).add(operation)


def _string_key(node: ast.Subscript) -> str | None:
    slice_node = node.slice

    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value

    return None


def _field_identifiers(node: ast.AST) -> set[str]:
    return {
        identifier
        for child in ast.walk(node)
        if isinstance(child, ast.Subscript)
        if (identifier := _string_key(child)) is not None
    }


def _operation(operator: ast.operator) -> UsageOperation | None:
    if isinstance(operator, ast.Add):
        return UsageOperation.ADD
    if isinstance(operator, ast.Sub):
        return UsageOperation.SUBTRACT
    if isinstance(operator, ast.Mult):
        return UsageOperation.MULTIPLY
    if isinstance(operator, ast.Div):
        return UsageOperation.DIVIDE
    return None
