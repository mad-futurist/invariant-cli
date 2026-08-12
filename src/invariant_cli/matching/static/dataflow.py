from __future__ import annotations

from dataclasses import dataclass

from invariant_cli.analysis.model import (
    CallResolutionKind,
    ProgramSemanticModel,
    ResolutionStatus,
    SemanticEdge,
    SemanticEdgeKind,
    SemanticFunction,
    SemanticNode,
    SemanticNodeKind,
    SemanticTerminalKind,
)

DEFAULT_MAX_CALL_DEPTH = 2


@dataclass(frozen=True)
class FieldFlowTrace:
    function: str
    field: str
    operations: tuple[str, ...]
    call_chain: tuple[str, ...] = ()
    terminal_kind: SemanticTerminalKind = SemanticTerminalKind.NONE
    terminal: str | None = None
    resolution: ResolutionStatus = ResolutionStatus.RESOLVED
    call_resolution: CallResolutionKind | None = None

    @property
    def flows_to_call(self) -> str | None:
        return self.call_chain[1] if len(self.call_chain) > 1 else None


@dataclass(frozen=True)
class ReturnContinuation:
    caller_function_id: str
    call_node_id: str


@dataclass(frozen=True)
class _WalkState:
    function_id: str
    node_id: str
    operations: tuple[str, ...]
    call_chain: tuple[str, ...]
    depth: int
    visited: frozenset[tuple[str, str]]
    resolution: ResolutionStatus
    return_stack: tuple[ReturnContinuation, ...] = ()


def trace_field_flows(
    model: ProgramSemanticModel,
    identifier: str,
    *,
    max_call_depth: int = DEFAULT_MAX_CALL_DEPTH,
) -> list[FieldFlowTrace]:
    if max_call_depth < 0:
        raise ValueError("max_call_depth cannot be negative.")
    traces: set[FieldFlowTrace] = set()

    for function in _unique_functions(model):
        reads = [
            node
            for node in model.function_nodes(function.id)
            if node.kind == SemanticNodeKind.STATE_READ
            and _field_identifier(node.label) == _field_identifier(identifier)
        ]
        for read in reads:
            traces.update(_trace_read(model, function, read, max_call_depth=max_call_depth))

    return sorted(traces, key=_trace_key)


def strongest_trace(traces: list[FieldFlowTrace]) -> FieldFlowTrace | None:
    if not traces:
        return None
    return max(
        traces,
        key=lambda trace: (
            trace.resolution == ResolutionStatus.RESOLVED,
            trace.terminal_kind == SemanticTerminalKind.STATE_WRITE,
            len(trace.operations),
            len(trace.call_chain),
            _trace_key(trace),
        ),
    )


def is_behavior_chain(trace: FieldFlowTrace) -> bool:
    return bool(trace.operations) and len(trace.call_chain) > 1


def traces_compatible(source: FieldFlowTrace, target: FieldFlowTrace) -> bool:
    return (
        source.resolution == ResolutionStatus.RESOLVED
        and target.resolution == ResolutionStatus.RESOLVED
        and is_behavior_chain(source)
        and is_behavior_chain(target)
        and source.operations == target.operations
        and source.terminal_kind == target.terminal_kind
    )


def _trace_read(
    model: ProgramSemanticModel,
    function: SemanticFunction,
    read: SemanticNode,
    *,
    max_call_depth: int,
) -> set[FieldFlowTrace]:
    nodes = {node.id: node for node in model.nodes}
    adjacency = _adjacency(model.edges)
    stack = [
        _WalkState(
            function_id=function.id,
            node_id=read.id,
            operations=(),
            call_chain=(function.name,),
            depth=0,
            visited=frozenset({(function.id, read.id)}),
            resolution=function.resolution,
        )
    ]
    traces: set[FieldFlowTrace] = set()

    while stack:
        state = stack.pop()
        node = nodes[state.node_id]
        terminal = _terminal(node)
        if terminal is not None:
            terminal_kind, label = terminal
            if terminal_kind == SemanticTerminalKind.RETURN and state.return_stack:
                continuation = state.return_stack[-1]
                caller = model.functions[continuation.caller_function_id]
                continuation_key = (caller.id, continuation.call_node_id)
                stack.append(
                    _WalkState(
                        function_id=caller.id,
                        node_id=continuation.call_node_id,
                        operations=state.operations,
                        call_chain=state.call_chain,
                        depth=max(state.depth - 1, 0),
                        visited=state.visited | {continuation_key},
                        resolution=state.resolution,
                        return_stack=state.return_stack[:-1],
                    )
                )
                continue
            traces.add(
                _trace(
                    function,
                    read,
                    state,
                    terminal_kind=terminal_kind,
                    terminal=label,
                )
            )
            continue

        outgoing = adjacency.get(state.node_id, [])
        if not outgoing:
            traces.add(_trace(function, read, state))
            continue

        for edge in outgoing:
            child = nodes[edge.target]
            operations = state.operations
            if child.kind == SemanticNodeKind.OPERATION:
                operations += (child.label,)

            if child.kind != SemanticNodeKind.CALL:
                _push_local(stack, state, child, operations)
                continue

            resolution = model.call_resolutions.get(child.id)
            if resolution is None or resolution.kind != CallResolutionKind.EXACT:
                kind = CallResolutionKind.EXTERNAL if resolution is None else resolution.kind
                traces.add(
                    _trace(
                        function,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (child.label,),
                        terminal_kind=SemanticTerminalKind.EXTERNAL_CALL,
                        terminal=child.label,
                        resolution=_unresolved_status(kind),
                        call_resolution=kind,
                    )
                )
                continue

            target_id = resolution.target_function_id
            callee = None if target_id is None else model.functions.get(target_id)
            if callee is None:
                traces.add(
                    _trace(
                        function,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (child.label,),
                        terminal_kind=SemanticTerminalKind.EXTERNAL_CALL,
                        terminal=child.label,
                        resolution=ResolutionStatus.UNRESOLVED,
                        call_resolution=CallResolutionKind.EXTERNAL,
                    )
                )
                continue

            if state.depth >= max_call_depth:
                traces.add(
                    _trace(
                        function,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (callee.name,),
                        terminal=child.label,
                        resolution=ResolutionStatus.PARTIAL,
                        call_resolution=CallResolutionKind.EXACT,
                    )
                )
                continue

            parameter = _callee_parameter(model, callee, edge)
            if parameter is None:
                traces.add(
                    _trace(
                        function,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (callee.name,),
                        terminal=child.label,
                        resolution=ResolutionStatus.UNRESOLVED,
                        call_resolution=CallResolutionKind.EXACT,
                    )
                )
                continue

            callee_key = (callee.id, parameter.id)
            if callee_key in state.visited:
                traces.add(
                    _trace(
                        function,
                        read,
                        state,
                        operations=operations,
                        call_chain=state.call_chain + (callee.name,),
                        terminal=child.label,
                        resolution=ResolutionStatus.PARTIAL,
                        call_resolution=CallResolutionKind.EXACT,
                    )
                )
                continue

            stack.append(
                _WalkState(
                    function_id=callee.id,
                    node_id=parameter.id,
                    operations=operations,
                    call_chain=state.call_chain + (callee.name,),
                    depth=state.depth + 1,
                    visited=state.visited | {callee_key},
                    resolution=_combine_resolution(state.resolution, callee.resolution),
                    return_stack=state.return_stack
                    + (
                        ReturnContinuation(
                            caller_function_id=state.function_id,
                            call_node_id=child.id,
                        ),
                    ),
                )
            )

    return traces


def _push_local(
    stack: list[_WalkState],
    state: _WalkState,
    child: SemanticNode,
    operations: tuple[str, ...],
) -> None:
    key = (state.function_id, child.id)
    if key in state.visited:
        return
    stack.append(
        _WalkState(
            function_id=state.function_id,
            node_id=child.id,
            operations=operations,
            call_chain=state.call_chain,
            depth=state.depth,
            visited=state.visited | {key},
            resolution=state.resolution,
            return_stack=state.return_stack,
        )
    )


def _callee_parameter(
    model: ProgramSemanticModel,
    callee: SemanticFunction,
    edge: SemanticEdge,
) -> SemanticNode | None:
    if edge.kind != SemanticEdgeKind.ARGUMENT_TO or edge.argument_slot is None:
        return None
    if edge.argument_slot >= len(callee.parameters):
        return None
    parameter_name = callee.parameters[edge.argument_slot]
    return next(
        (
            node
            for node in model.function_nodes(callee.id)
            if node.kind == SemanticNodeKind.PARAMETER and node.label == parameter_name
        ),
        None,
    )


def _terminal(node: SemanticNode) -> tuple[SemanticTerminalKind, str] | None:
    if node.kind == SemanticNodeKind.STATE_WRITE:
        return SemanticTerminalKind.STATE_WRITE, node.label
    if node.kind == SemanticNodeKind.RETURN:
        return SemanticTerminalKind.RETURN, node.label
    return None


def _trace(
    origin: SemanticFunction,
    read: SemanticNode,
    state: _WalkState,
    *,
    operations: tuple[str, ...] | None = None,
    call_chain: tuple[str, ...] | None = None,
    terminal_kind: SemanticTerminalKind = SemanticTerminalKind.NONE,
    terminal: str | None = None,
    resolution: ResolutionStatus | None = None,
    call_resolution: CallResolutionKind | None = None,
) -> FieldFlowTrace:
    return FieldFlowTrace(
        function=origin.id,
        field=read.label,
        operations=state.operations if operations is None else operations,
        call_chain=state.call_chain if call_chain is None else call_chain,
        terminal_kind=terminal_kind,
        terminal=terminal,
        resolution=state.resolution if resolution is None else resolution,
        call_resolution=call_resolution,
    )


def _adjacency(edges: list[SemanticEdge]) -> dict[str, list[SemanticEdge]]:
    result: dict[str, list[SemanticEdge]] = {}
    for edge in edges:
        result.setdefault(edge.source, []).append(edge)
    return result


def _unique_functions(model: ProgramSemanticModel) -> list[SemanticFunction]:
    return [model.functions[key] for key in sorted(model.functions)]


def _unresolved_status(kind: CallResolutionKind) -> ResolutionStatus:
    if kind in {CallResolutionKind.HEURISTIC, CallResolutionKind.AMBIGUOUS}:
        return ResolutionStatus.PARTIAL
    return ResolutionStatus.UNRESOLVED


def _combine_resolution(
    left: ResolutionStatus,
    right: ResolutionStatus,
) -> ResolutionStatus:
    order = {
        ResolutionStatus.RESOLVED: 0,
        ResolutionStatus.PARTIAL: 1,
        ResolutionStatus.UNRESOLVED: 2,
    }
    return left if order[left] >= order[right] else right


def _trace_key(trace: FieldFlowTrace) -> tuple[object, ...]:
    return (
        trace.function,
        trace.field,
        trace.operations,
        trace.call_chain,
        trace.terminal_kind.value,
        trace.terminal or "",
        trace.resolution.value,
        "" if trace.call_resolution is None else trace.call_resolution.value,
    )


def _field_identifier(label: str) -> str:
    return label.rsplit(".", 1)[-1]
