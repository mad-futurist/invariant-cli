from dataclasses import replace

from invariant_cli.contracts.model import CorrespondenceCandidate
from invariant_cli.matching.model import EntityKind, EvidenceKind
from invariant_cli.matching.static.matcher import (
    DATA_FLOW_PRODUCER,
    PRODUCER,
    build_static_data_flow_evidence,
    build_static_usage_evidence,
)
from invariant_cli.matching.static.model import FieldUsage, FunctionFlow


def enrich_with_static_usage(
    candidates: list[CorrespondenceCandidate],
    source_usage: dict[str, FieldUsage],
    target_usage: dict[str, FieldUsage],
) -> list[CorrespondenceCandidate]:
    enriched: list[CorrespondenceCandidate] = []

    for candidate in candidates:
        if (
            candidate.source.kind != EntityKind.JSON_FIELD
            or candidate.target.kind != EntityKind.JSON_FIELD
        ):
            enriched.append(candidate)
            continue

        source = source_usage.get(candidate.source.identifier)
        target = target_usage.get(candidate.target.identifier)

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
    source_flows: list[FunctionFlow],
    target_flows: list[FunctionFlow],
) -> list[CorrespondenceCandidate]:
    enriched: list[CorrespondenceCandidate] = []

    for candidate in candidates:
        evidence = [
            item
            for item in candidate.evidence
            if not (
                item.kind == EvidenceKind.STATIC_DATA_FLOW and item.producer == DATA_FLOW_PRODUCER
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
        enriched.append(replace(candidate, evidence=evidence))

    return enriched
