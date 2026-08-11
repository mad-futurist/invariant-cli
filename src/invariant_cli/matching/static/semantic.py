from contextlib import suppress

from invariant_cli.analysis.model import (
    ProgramSemanticModel,
    SemanticNode,
    SemanticNodeKind,
)
from invariant_cli.matching.static.model import FieldUsage, UsageOperation


def extract_semantic_usage(model: ProgramSemanticModel) -> dict[str, FieldUsage]:
    operations: dict[str, set[UsageOperation]] = {}
    nodes = {node.id: node for node in model.nodes}
    adjacency: dict[str, list[str]] = {}
    for edge in model.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)

    for node in model.nodes:
        if node.kind == SemanticNodeKind.STATE_READ:
            identifier = _field_identifier(node.label)
            operations.setdefault(identifier, set()).add(UsageOperation.READ)
            operations[identifier].update(_reachable_operations(node, nodes, adjacency))
        elif node.kind == SemanticNodeKind.STATE_WRITE:
            identifier = _field_identifier(node.label)
            operations.setdefault(identifier, set()).add(UsageOperation.WRITE)

    return {
        identifier: FieldUsage(identifier, field_operations)
        for identifier, field_operations in sorted(operations.items())
    }


def _reachable_operations(
    origin: SemanticNode,
    nodes: dict[str, SemanticNode],
    adjacency: dict[str, list[str]],
) -> set[UsageOperation]:
    found: set[UsageOperation] = set()
    stack = list(adjacency.get(origin.id, []))
    visited = {origin.id}
    while stack:
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        node = nodes[node_id]
        if node.function_id != origin.function_id:
            continue
        if node.kind == SemanticNodeKind.OPERATION:
            with suppress(ValueError):
                found.add(UsageOperation(node.label))
        stack.extend(adjacency.get(node_id, []))
    return found


def _field_identifier(label: str) -> str:
    return label.rsplit(".", 1)[-1]
