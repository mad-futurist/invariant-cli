from __future__ import annotations

from dataclasses import dataclass

from invariant_cli.matching.static.model import (
    AnalysisResolution,
    FlowEdge,
    FlowEdgeKind,
    FlowNode,
    FlowNodeKind,
    FlowTerminalKind,
    FunctionFlow,
)
from invariant_cli.matching.static.program import ProgramIndex

DEFAULT_MAX_CALL_DEPTH = 2


@dataclass(frozen=True)
class FieldFlowTrace:
    function: str
    field: str
    operations: tuple[str, ...]
    call_chain: tuple[str, ...] = ()
    terminal_kind: FlowTerminalKind = FlowTerminalKind.NONE
    terminal: str | None = None
    resolution: AnalysisResolution = AnalysisResolution.RESOLVED

    @property
    def flows_to_call(self) -> str | None:
        return self.call_chain[1] if len(self.call_chain) > 1 else None


@dataclass(frozen=True)
class _WalkState:
    flow: FunctionFlow
    node_id: str
    operations: tuple[str, ...]
    call_chain: tuple[str, ...]
    depth: int
    visited: frozenset[tuple[str, str]]
    unresolved: bool


def trace_field_flows(
    program_or_flows: ProgramIndex | list[FunctionFlow],
    identifier: str,
    *,
    max_call_depth: int = DEFAULT_MAX_CALL_DEPTH,
) -> list[FieldFlowTrace]:
    if max_call_depth < 0:
        raise ValueError("max_call_depth cannot be negative.")
    program = (
        program_or_flows
        if isinstance(program_or_flows, ProgramIndex)
        else ProgramIndex.from_flows(program_or_flows)
    )
    traces: set[FieldFlowTrace] = set()

    for flow in _unique_flows(program):
        reads = [
            node
            for node in flow.nodes
            if node.kind == FlowNodeKind.FIELD_READ
            and _field_identifier(node.label) == _field_identifier(identifier)
        ]
        for read in reads:
            traces.update(
                _trace_read(
                    program,
                    flow,
                    read,
                    max_call_depth=max_call_depth,
                )
            )

    return sorted(traces, key=_trace_key)


def strongest_trace(traces: list[FieldFlowTrace]) -> FieldFlowTrace | None:
    if not traces:
        return None
    return max(
        traces,
        key=lambda trace: (
            trace.resolution == AnalysisResolution.RESOLVED,
            trace.terminal_kind == FlowTerminalKind.FIELD_WRITE,
            len(trace.operations),
            len(trace.call_chain),
            _trace_key(trace),
        ),
    )


def is_behavior_chain(trace: FieldFlowTrace) -> bool:
    return bool(trace.operations) and len(trace.call_chain) > 1


def traces_compatible(source: FieldFlowTrace, target: FieldFlowTrace) -> bool:
    return (
        source.resolution == AnalysisResolution.RESOLVED
        and target.resolution == AnalysisResolution.RESOLVED
        and is_behavior_chain(source)
        and is_behavior_chain(target)
        and source.operations == target.operations
        and source.terminal_kind == target.terminal_kind
    )


def _trace_read(
    program: ProgramIndex,
    flow: FunctionFlow,
    read: FlowNode,
    *,
    max_call_depth: int,
) -> set[FieldFlowTrace]:
    function = _function_label(flow)
    stack = [
        _WalkState(
            flow=flow,
            node_id=read.id,
            operations=(),
            call_chain=(flow.function.name,),
            depth=0,
            visited=frozenset({(function, read.id)}),
            unresolved=flow.resolution != AnalysisResolution.RESOLVED,
        )
    ]
    traces: set[FieldFlowTrace] = set()

    while stack:
        state = stack.pop()
        nodes = {node.id: node for node in state.flow.nodes}
        node = nodes[state.node_id]

        terminal = _terminal(node)
        if terminal is not None:
            terminal_kind, label = terminal
            traces.add(
                _trace(
                    flow,
                    read,
                    state,
                    terminal_kind=terminal_kind,
                    terminal=label,
                )
            )
            continue

        outgoing = [edge for edge in state.flow.edges if edge.source == state.node_id]
        if not outgoing:
            traces.add(_trace(flow, read, state))
            continue

        for edge in outgoing:
            child = nodes[edge.target]
            operations = state.operations
            if child.kind == FlowNodeKind.OPERATION:
                operations += (child.label,)

            if child.kind != FlowNodeKind.CALL:
                _push_local(stack, state, child, operations)
                continue

            callee = program.resolve(child.label)
            if callee is None:
                traces.add(
                    _trace(
                        flow,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (child.label,),
                        terminal_kind=FlowTerminalKind.EXTERNAL_CALL,
                        terminal=child.label,
                        resolution=AnalysisResolution.UNRESOLVED,
                    )
                )
                continue

            if state.depth >= max_call_depth:
                traces.add(
                    _trace(
                        flow,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (callee.function.name,),
                        terminal=child.label,
                        resolution=AnalysisResolution.DEPTH_LIMIT,
                    )
                )
                continue

            parameter = _callee_parameter(callee, edge)
            if parameter is None:
                traces.add(
                    _trace(
                        flow,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (callee.function.name,),
                        terminal=child.label,
                        resolution=AnalysisResolution.UNRESOLVED,
                    )
                )
                continue

            callee_key = (_function_label(callee), parameter.id)
            if callee_key in state.visited:
                traces.add(
                    _trace(
                        flow,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (callee.function.name,),
                        terminal=child.label,
                        resolution=AnalysisResolution.DEPTH_LIMIT,
                    )
                )
                continue

            stack.append(
                _WalkState(
                    flow=callee,
                    node_id=parameter.id,
                    operations=operations,
                    call_chain=state.call_chain + (callee.function.name,),
                    depth=state.depth + 1,
                    visited=state.visited | {callee_key},
                    unresolved=(
                        state.unresolved or callee.resolution != AnalysisResolution.RESOLVED
                    ),
                )
            )

    return traces


def _push_local(
    stack: list[_WalkState],
    state: _WalkState,
    child: FlowNode,
    operations: tuple[str, ...],
) -> None:
    key = (_function_label(state.flow), child.id)
    if key in state.visited:
        return
    stack.append(
        _WalkState(
            flow=state.flow,
            node_id=child.id,
            operations=operations,
            call_chain=state.call_chain,
            depth=state.depth,
            visited=state.visited | {key},
            unresolved=state.unresolved,
        )
    )


def _callee_parameter(callee: FunctionFlow, edge: FlowEdge) -> FlowNode | None:
    if edge.kind != FlowEdgeKind.ARGUMENT_TO or edge.argument_slot is None:
        return None
    if edge.argument_slot >= len(callee.parameters):
        return None
    parameter_name = callee.parameters[edge.argument_slot]
    return next(
        (
            node
            for node in callee.nodes
            if node.kind == FlowNodeKind.PARAMETER and node.label == parameter_name
        ),
        None,
    )


def _terminal(node: FlowNode) -> tuple[FlowTerminalKind, str] | None:
    if node.kind == FlowNodeKind.FIELD_WRITE:
        return FlowTerminalKind.FIELD_WRITE, node.label
    if node.kind == FlowNodeKind.RETURN:
        return FlowTerminalKind.RETURN, node.label
    return None


def _trace(
    origin: FunctionFlow,
    read: FlowNode,
    state: _WalkState,
    *,
    operations: tuple[str, ...] | None = None,
    call_chain: tuple[str, ...] | None = None,
    terminal_kind: FlowTerminalKind = FlowTerminalKind.NONE,
    terminal: str | None = None,
    resolution: AnalysisResolution = AnalysisResolution.RESOLVED,
) -> FieldFlowTrace:
    trace_resolution = resolution
    if trace_resolution == AnalysisResolution.RESOLVED and state.unresolved:
        trace_resolution = AnalysisResolution.UNRESOLVED
    return FieldFlowTrace(
        function=_function_label(origin),
        field=read.label,
        operations=state.operations if operations is None else operations,
        call_chain=state.call_chain if call_chain is None else call_chain,
        terminal_kind=terminal_kind,
        terminal=terminal,
        resolution=trace_resolution,
    )


def _unique_flows(program: ProgramIndex) -> list[FunctionFlow]:
    return [program.functions[key] for key in sorted(program.functions)]


def _trace_key(trace: FieldFlowTrace) -> tuple[object, ...]:
    return (
        trace.function,
        trace.field,
        trace.operations,
        trace.call_chain,
        trace.terminal_kind.value,
        trace.terminal or "",
        trace.resolution.value,
    )


def _field_identifier(label: str) -> str:
    return label.rsplit(".", 1)[-1]


def _function_label(flow: FunctionFlow) -> str:
    return f"{flow.function.module}.{flow.function.name}"
