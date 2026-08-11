from __future__ import annotations

from dataclasses import dataclass

from invariant_cli.matching.static.model import (
    FlowNodeKind,
    FunctionFlow,
)


@dataclass(frozen=True)
class FieldFlowTrace:
    function: str
    field: str
    operations: tuple[str, ...]
    flows_to_call: str | None


def trace_field_flows(flows: list[FunctionFlow], identifier: str) -> list[FieldFlowTrace]:
    traces: set[FieldFlowTrace] = set()

    for flow in flows:
        nodes = {node.id: node for node in flow.nodes}
        adjacency: dict[str, list[str]] = {}
        for edge in flow.edges:
            adjacency.setdefault(edge.source, []).append(edge.target)

        reads = [
            node
            for node in flow.nodes
            if node.kind == FlowNodeKind.FIELD_READ
            and _field_identifier(node.label) == _field_identifier(identifier)
        ]
        for read in reads:
            terminal_found = False
            stack: list[tuple[str, tuple[str, ...], frozenset[str]]] = [
                (read.id, (), frozenset({read.id}))
            ]
            while stack:
                node_id, operations, visited = stack.pop()
                children = adjacency.get(node_id, [])
                if not children:
                    if operations:
                        traces.add(
                            FieldFlowTrace(
                                function=_function_label(flow),
                                field=read.label,
                                operations=operations,
                                flows_to_call=None,
                            )
                        )
                    continue

                for child_id in children:
                    if child_id in visited:
                        continue
                    child = nodes[child_id]
                    child_operations = operations
                    if child.kind == FlowNodeKind.OPERATION:
                        child_operations += (child.label,)
                    if child.kind == FlowNodeKind.CALL:
                        terminal_found = True
                        traces.add(
                            FieldFlowTrace(
                                function=_function_label(flow),
                                field=read.label,
                                operations=child_operations,
                                flows_to_call=child.label,
                            )
                        )
                        continue
                    stack.append((child_id, child_operations, visited | {child_id}))

            if not terminal_found and not any(trace.field == read.label for trace in traces):
                traces.add(
                    FieldFlowTrace(
                        function=_function_label(flow),
                        field=read.label,
                        operations=(),
                        flows_to_call=None,
                    )
                )

    return sorted(
        traces,
        key=lambda trace: (
            trace.function,
            trace.field,
            trace.operations,
            trace.flows_to_call or "",
        ),
    )


def strongest_trace(traces: list[FieldFlowTrace]) -> FieldFlowTrace | None:
    if not traces:
        return None
    return max(
        traces,
        key=lambda trace: (
            len(trace.operations),
            trace.flows_to_call is not None,
            trace.operations,
            trace.flows_to_call or "",
        ),
    )


def is_behavior_chain(trace: FieldFlowTrace) -> bool:
    return bool(trace.operations) and trace.flows_to_call is not None


def traces_compatible(source: FieldFlowTrace, target: FieldFlowTrace) -> bool:
    return (
        is_behavior_chain(source)
        and is_behavior_chain(target)
        and source.operations == target.operations
    )


def _field_identifier(label: str) -> str:
    return label.rsplit(".", 1)[-1]


def _function_label(flow: FunctionFlow) -> str:
    return f"{flow.function.module}.{flow.function.name}"
