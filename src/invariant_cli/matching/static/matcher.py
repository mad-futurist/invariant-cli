from __future__ import annotations

from collections.abc import Callable

from invariant_cli.analysis.model import (
    CallResolutionKind,
    ProgramSemanticModel,
    ResolutionStatus,
    SemanticTerminalKind,
)
from invariant_cli.matching.model import (
    EntityRef,
    Evidence,
    EvidenceEffect,
    EvidenceFamily,
    EvidenceKind,
)
from invariant_cli.matching.static.dataflow import (
    FieldFlowTrace,
    is_behavior_chain,
    strongest_trace,
    trace_field_flows,
    traces_compatible,
)
from invariant_cli.matching.static.model import FieldUsage

PRODUCER = "python-ast-v1"
DATA_FLOW_PRODUCER = "python-dataflow-v1"
CALL_CONTEXT_PRODUCER = "python-call-context-v1"


def compare_usage(source: FieldUsage, target: FieldUsage) -> dict[str, object]:
    common = source.operations & target.operations

    return {
        "source_operations": sorted(operation.value for operation in source.operations),
        "target_operations": sorted(operation.value for operation in target.operations),
        "common_operations": sorted(operation.value for operation in common),
    }


def build_static_usage_evidence(source: FieldUsage, target: FieldUsage) -> Evidence | None:
    common = source.operations & target.operations

    if not common:
        return None

    return Evidence(
        kind=EvidenceKind.STATIC_USAGE,
        producer=PRODUCER,
        family=EvidenceFamily.STATIC_PROGRAM,
        attributes=compare_usage(source, target),
    )


def build_static_data_flow_evidence(
    source_entity: EntityRef,
    target_entity: EntityRef,
    source_program: ProgramSemanticModel,
    target_program: ProgramSemanticModel,
) -> Evidence | None:
    match = _match_field_traces(
        source_entity,
        target_entity,
        source_program,
        target_program,
        compatible=_local_data_flow_compatible,
    )
    if match is None:
        return None
    effect, source_trace, target_trace, reason = match
    return Evidence(
        kind=EvidenceKind.STATIC_DATA_FLOW,
        producer=DATA_FLOW_PRODUCER,
        family=EvidenceFamily.STATIC_PROGRAM,
        effect=effect,
        attributes={
            "source": _trace_attributes(source_entity, source_trace),
            "target": _trace_attributes(target_entity, target_trace),
            "reason": reason,
        },
    )


def build_call_context_evidence(
    source_entity: EntityRef,
    target_entity: EntityRef,
    source_program: ProgramSemanticModel,
    target_program: ProgramSemanticModel,
) -> Evidence | None:
    match = _match_field_traces(
        source_entity,
        target_entity,
        source_program,
        target_program,
        compatible=traces_compatible,
    )
    if match is None:
        return None
    effect, source_trace, target_trace, reason = match
    return Evidence(
        kind=EvidenceKind.CALL_CONTEXT,
        producer=CALL_CONTEXT_PRODUCER,
        family=EvidenceFamily.STATIC_PROGRAM,
        effect=effect,
        attributes={
            "source_call_chain": list(source_trace.call_chain),
            "target_call_chain": list(target_trace.call_chain),
            "source_terminal": source_trace.terminal_kind.value,
            "target_terminal": target_trace.terminal_kind.value,
            "source_resolution": source_trace.resolution.value,
            "target_resolution": target_trace.resolution.value,
            "reason": reason,
        },
    )


def _match_field_traces(
    source_entity: EntityRef,
    target_entity: EntityRef,
    source_program: ProgramSemanticModel,
    target_program: ProgramSemanticModel,
    *,
    compatible: Callable[[FieldFlowTrace, FieldFlowTrace], bool],
) -> tuple[EvidenceEffect, FieldFlowTrace, FieldFlowTrace, str] | None:
    source_traces = trace_field_flows(source_program, source_entity.logical_state)
    target_traces = trace_field_flows(target_program, target_entity.logical_state)
    source_chain = strongest_trace([trace for trace in source_traces if is_behavior_chain(trace)])
    if source_chain is None or not target_traces:
        return None

    compatible_pairs = [
        (source, target)
        for source in source_traces
        for target in target_traces
        if compatible(source, target)
    ]
    if compatible_pairs:
        source_trace, target_trace = max(
            compatible_pairs,
            key=lambda pair: (
                len(pair[0].operations),
                len(pair[0].call_chain),
                pair[0].function,
                pair[1].function,
            ),
        )
        return (
            EvidenceEffect.SUPPORTS,
            source_trace,
            target_trace,
            "compatible_resolved_behavior_chain",
        )

    unresolved = [
        trace
        for trace in [*source_traces, *target_traces]
        if trace.resolution != ResolutionStatus.RESOLVED
    ]
    if unresolved:
        unresolved_trace = strongest_trace(unresolved)
        source_trace = _preferred_trace(source_traces, source_chain)
        target_trace = _preferred_trace(target_traces, unresolved_trace)
        if (
            unresolved_trace is not None
            and unresolved_trace.resolution == ResolutionStatus.PARTIAL
            and unresolved_trace.call_resolution == CallResolutionKind.EXACT
        ):
            reason = "call_depth_limit_reached"
        elif (
            unresolved_trace is not None
            and unresolved_trace.call_resolution == CallResolutionKind.HEURISTIC
        ):
            reason = "heuristic_call_resolution"
        elif (
            unresolved_trace is not None
            and unresolved_trace.call_resolution == CallResolutionKind.AMBIGUOUS
        ):
            reason = "ambiguous_call_resolution"
        elif (
            unresolved_trace is not None
            and unresolved_trace.terminal_kind == SemanticTerminalKind.EXTERNAL_CALL
        ):
            reason = "unresolved_external_call"
        else:
            reason = "unsupported_syntax_or_alias"
        return EvidenceEffect.NEUTRAL, source_trace, target_trace, reason

    strongest_target = strongest_trace(target_traces)
    if strongest_target is None:
        return None
    return (
        EvidenceEffect.CONTRADICTS,
        source_chain,
        strongest_target,
        "incompatible_fully_resolved_behavior_chain",
    )


def _preferred_trace(
    traces: list[FieldFlowTrace],
    fallback: FieldFlowTrace | None,
) -> FieldFlowTrace:
    unresolved = strongest_trace(
        [trace for trace in traces if trace.resolution != ResolutionStatus.RESOLVED]
    )
    selected = unresolved or fallback or strongest_trace(traces)
    if selected is None:
        raise ValueError("A preferred trace requires at least one trace.")
    return selected


def _local_data_flow_compatible(source: FieldFlowTrace, target: FieldFlowTrace) -> bool:
    return (
        source.resolution == ResolutionStatus.RESOLVED
        and target.resolution == ResolutionStatus.RESOLVED
        and is_behavior_chain(source)
        and is_behavior_chain(target)
        and source.operations == target.operations
    )


def _trace_attributes(entity: EntityRef, trace: FieldFlowTrace) -> dict[str, object]:
    return {
        "function": trace.function,
        "reads_from": entity.locator,
        "operations": list(trace.operations),
        "flows_to_call": trace.flows_to_call,
        "call_chain": list(trace.call_chain),
        "terminal_kind": trace.terminal_kind.value,
        "terminal": trace.terminal,
        "resolution": trace.resolution.value,
        "call_resolution": (None if trace.call_resolution is None else trace.call_resolution.value),
    }
