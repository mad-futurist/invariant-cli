from contextlib import suppress

from invariant_cli.analysis.model import (
    ProgramSemanticModel,
    SemanticNode,
    SemanticNodeKind,
)
from invariant_cli.matching.model import LogicalStateIdentity
from invariant_cli.matching.static.model import FieldUsage, UsageOperation


def extract_semantic_usage(
    model: ProgramSemanticModel,
) -> dict[LogicalStateIdentity, FieldUsage]:
    operations: dict[LogicalStateIdentity, set[UsageOperation]] = {}
    nodes = {node.id: node for node in model.nodes}
    adjacency: dict[str, list[str]] = {}
    for edge in model.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)

    for node in model.nodes:
        if node.kind == SemanticNodeKind.STATE_READ:
            state = LogicalStateIdentity.from_semantic_label(node.label)
            operations.setdefault(state, set()).add(UsageOperation.READ)
            operations[state].update(_reachable_operations(node, nodes, adjacency))
        elif node.kind == SemanticNodeKind.STATE_WRITE:
            state = LogicalStateIdentity.from_semantic_label(node.label)
            operations.setdefault(state, set()).add(UsageOperation.WRITE)

    return {
        state: FieldUsage(state.locator, field_operations)
        for state, field_operations in sorted(operations.items())
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
