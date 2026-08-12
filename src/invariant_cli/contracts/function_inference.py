from __future__ import annotations

from invariant_cli.analysis.model import ProgramSemanticModel, ResolutionStatus
from invariant_cli.analysis.signatures import (
    FunctionBehaviorSignature,
    build_function_signatures,
)
from invariant_cli.contracts.model import (
    CorrespondenceCandidate,
    FunctionCorrespondenceCandidate,
    FunctionCorrespondenceStatus,
)
from invariant_cli.matching.model import (
    EntityRef,
    Evidence,
    EvidenceEffect,
    EvidenceFamily,
    EvidenceKind,
)

PRODUCER = "function-behavior-v1"


def infer_function_correspondences(
    source_program: ProgramSemanticModel,
    target_program: ProgramSemanticModel,
    field_correspondences: list[CorrespondenceCandidate],
) -> list[FunctionCorrespondenceCandidate]:
    source_signatures = build_function_signatures(source_program)
    target_signatures = build_function_signatures(target_program)
    field_map = {
        candidate.source.identifier: candidate.target for candidate in field_correspondences
    }
    source_fields = {
        candidate.source.identifier: candidate.source for candidate in field_correspondences
    }
    results: list[FunctionCorrespondenceCandidate] = []

    for source_id, source in source_signatures.items():
        mapped_identifiers = {
            field_map[identifier].identifier
            for identifier in (*source.state_reads, *source.state_writes)
            if identifier in field_map
        }
        if not mapped_identifiers:
            continue

        for target_id, target in target_signatures.items():
            touched = set(target.state_reads) | set(target.state_writes)
            if not (mapped_identifiers & touched):
                continue
            mapped_reads = _mapped_pairs(
                source.state_reads,
                target.state_reads,
                source_fields,
                field_map,
            )
            mapped_writes = _mapped_pairs(
                source.state_writes,
                target.state_writes,
                source_fields,
                field_map,
            )
            effect = _effect(source, target, mapped_reads, mapped_writes)
            evidence = Evidence(
                kind=EvidenceKind.FUNCTION_BEHAVIOR,
                producer=PRODUCER,
                family=EvidenceFamily.STATIC_PROGRAM,
                effect=effect,
                attributes={
                    "source_function": source_id,
                    "target_function": target_id,
                    "source_operations": list(source.operations),
                    "target_operations": list(target.operations),
                    "source_effects": _effects(source),
                    "target_effects": _effects(target),
                    "source_resolution": source.resolution.value,
                    "target_resolution": target.resolution.value,
                },
            )
            results.append(
                FunctionCorrespondenceCandidate(
                    source=source.function,
                    target=target.function,
                    evidence=[evidence],
                    mapped_state_reads=mapped_reads,
                    mapped_state_writes=mapped_writes,
                    status={
                        EvidenceEffect.SUPPORTS: FunctionCorrespondenceStatus.CANDIDATE,
                        EvidenceEffect.CONTRADICTS: FunctionCorrespondenceStatus.REJECTED,
                        EvidenceEffect.NEUTRAL: FunctionCorrespondenceStatus.INCONCLUSIVE,
                    }[effect],
                )
            )

    return sorted(
        results,
        key=lambda item: (
            item.source.locator,
            item.status != FunctionCorrespondenceStatus.CANDIDATE,
            item.target.locator,
        ),
    )


def _mapped_pairs(
    source_identifiers: tuple[str, ...],
    target_identifiers: tuple[str, ...],
    source_fields: dict[str, EntityRef],
    field_map: dict[str, EntityRef],
) -> tuple[tuple[EntityRef, EntityRef], ...]:
    targets = set(target_identifiers)
    return tuple(
        (source_fields[identifier], field_map[identifier])
        for identifier in source_identifiers
        if identifier in field_map and field_map[identifier].identifier in targets
    )


def _effect(
    source: FunctionBehaviorSignature,
    target: FunctionBehaviorSignature,
    mapped_reads: tuple[tuple[EntityRef, EntityRef], ...],
    mapped_writes: tuple[tuple[EntityRef, EntityRef], ...],
) -> EvidenceEffect:
    if (
        source.resolution != ResolutionStatus.RESOLVED
        or target.resolution != ResolutionStatus.RESOLVED
    ):
        return EvidenceEffect.NEUTRAL
    reads_covered = len(mapped_reads) == len(source.state_reads)
    writes_covered = len(mapped_writes) == len(source.state_writes)
    operations_match = source.operations == target.operations
    if reads_covered and writes_covered and operations_match:
        return EvidenceEffect.SUPPORTS
    return EvidenceEffect.CONTRADICTS


def _effects(signature: FunctionBehaviorSignature) -> list[dict[str, str]]:
    return [
        {"kind": effect.kind, "target": effect.target, "owner_function": effect.owner_function}
        for effect in signature.effects
    ]
