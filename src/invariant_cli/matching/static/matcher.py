from invariant_cli.matching.model import EntityRef, Evidence, EvidenceEffect, EvidenceKind
from invariant_cli.matching.static.dataflow import (
    FieldFlowTrace,
    is_behavior_chain,
    strongest_trace,
    trace_field_flows,
    traces_compatible,
)
from invariant_cli.matching.static.model import FieldUsage, FunctionFlow

PRODUCER = "python-ast-v1"
DATA_FLOW_PRODUCER = "python-dataflow-v1"


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
        attributes=compare_usage(source, target),
    )


def build_static_data_flow_evidence(
    source_entity: EntityRef,
    target_entity: EntityRef,
    source_flows: list[FunctionFlow],
    target_flows: list[FunctionFlow],
) -> Evidence | None:
    source_traces = trace_field_flows(source_flows, source_entity.identifier)
    target_traces = trace_field_flows(target_flows, target_entity.identifier)
    source_chain = strongest_trace([trace for trace in source_traces if is_behavior_chain(trace)])

    if source_chain is None or not target_traces:
        return None

    compatible_pairs = [
        (source, target)
        for source in source_traces
        for target in target_traces
        if traces_compatible(source, target)
    ]
    if compatible_pairs:
        source_trace, target_trace = max(
            compatible_pairs,
            key=lambda pair: (
                len(pair[0].operations),
                pair[0].function,
                pair[1].function,
            ),
        )
        effect = EvidenceEffect.SUPPORTS
        reason = "compatible_behavior_chain"
    else:
        source_trace = source_chain
        strongest_target = strongest_trace(target_traces)
        if strongest_target is None:
            return None
        target_trace = strongest_target
        effect = EvidenceEffect.CONTRADICTS
        reason = "target_field_not_in_compatible_computation_call_chain"

    return Evidence(
        kind=EvidenceKind.STATIC_DATA_FLOW,
        producer=DATA_FLOW_PRODUCER,
        effect=effect,
        attributes={
            "source": _trace_attributes(source_entity, source_trace),
            "target": _trace_attributes(target_entity, target_trace),
            "reason": reason,
        },
    )


def _trace_attributes(entity: EntityRef, trace: FieldFlowTrace) -> dict[str, object]:
    return {
        "function": trace.function,
        "reads_from": entity.locator,
        "operations": list(trace.operations),
        "flows_to_call": trace.flows_to_call,
    }
