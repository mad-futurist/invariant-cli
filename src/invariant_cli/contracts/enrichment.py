from dataclasses import replace

from invariant_cli.analysis.model import ProgramSemanticModel
from invariant_cli.contracts.model import CorrespondenceCandidate
from invariant_cli.matching.model import EntityKind, EvidenceKind, LogicalStateIdentity
from invariant_cli.matching.static.matcher import (
    CALL_CONTEXT_PRODUCER,
    DATA_FLOW_PRODUCER,
    PRODUCER,
    build_call_context_evidence,
    build_static_data_flow_evidence,
    build_static_usage_evidence,
)
from invariant_cli.matching.static.model import FieldUsage


def enrich_with_static_usage(
    candidates: list[CorrespondenceCandidate],
    source_usage: dict[LogicalStateIdentity, FieldUsage],
    target_usage: dict[LogicalStateIdentity, FieldUsage],
) -> list[CorrespondenceCandidate]:
    enriched: list[CorrespondenceCandidate] = []

    for candidate in candidates:
        if (
            candidate.source.kind != EntityKind.JSON_FIELD
            or candidate.target.kind != EntityKind.JSON_FIELD
        ):
            enriched.append(candidate)
            continue

        source = source_usage.get(candidate.source.logical_state)
        target = target_usage.get(candidate.target.logical_state)

        if source is None or target is None:
            enriched.append(candidate)
            continue

        static_evidence = build_static_usage_evidence(source, target)

        if static_evidence is None:
            enriched.append(candidate)
            continue

        evidence = [
            item
            for item in candidate.evidence
            if not (item.kind == EvidenceKind.STATIC_USAGE and item.producer == PRODUCER)
        ]
        evidence.append(static_evidence)

        enriched.append(replace(candidate, evidence=evidence))

    return enriched


def enrich_with_static_data_flow(
    candidates: list[CorrespondenceCandidate],
    source_flows: ProgramSemanticModel,
    target_flows: ProgramSemanticModel,
) -> list[CorrespondenceCandidate]:
    enriched: list[CorrespondenceCandidate] = []

    for candidate in candidates:
        evidence = [
            item
            for item in candidate.evidence
            if not (
                (item.kind == EvidenceKind.STATIC_DATA_FLOW and item.producer == DATA_FLOW_PRODUCER)
                or (
                    item.kind == EvidenceKind.CALL_CONTEXT
                    and item.producer == CALL_CONTEXT_PRODUCER
                )
            )
        ]
        data_flow_evidence = build_static_data_flow_evidence(
            candidate.source,
            candidate.target,
            source_flows,
            target_flows,
        )
        if data_flow_evidence is not None:
            evidence.append(data_flow_evidence)
        call_context_evidence = build_call_context_evidence(
            candidate.source,
            candidate.target,
            source_flows,
            target_flows,
        )
        if call_context_evidence is not None:
            evidence.append(call_context_evidence)
        enriched.append(replace(candidate, evidence=evidence))

    return enriched
