from __future__ import annotations

from dataclasses import dataclass, replace

from invariant_cli.analysis.model import ProgramSemanticModel, ResolutionStatus
from invariant_cli.analysis.signatures import FunctionBehaviorSignature, build_function_signatures
from invariant_cli.contracts.model import (
    CandidateSet,
    CandidateSetStatus,
    CandidateShape,
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
    LogicalStateIdentity,
)

PRODUCER = "function-behavior-v2"


@dataclass(frozen=True)
class SelectedStateMapping:
    source: EntityRef
    target: EntityRef
    resolved: bool


@dataclass(frozen=True)
class FunctionCompatibilityPolicy:
    allowed_extra_effects: frozenset[tuple[str, LogicalStateIdentity]] = frozenset()


DEFAULT_COMPATIBILITY_POLICY = FunctionCompatibilityPolicy()


def select_state_mappings(candidate_sets: list[CandidateSet]) -> tuple[SelectedStateMapping, ...]:
    selected: list[SelectedStateMapping] = []
    for candidate_set in candidate_sets:
        if candidate_set.status == CandidateSetStatus.WELL_SUPPORTED_CANDIDATE:
            ranked = candidate_set.candidates[:1]
            resolved = True
        elif candidate_set.status == CandidateSetStatus.AMBIGUOUS:
            ranked = [item for item in candidate_set.candidates if item.rank == 1]
            resolved = False
        else:
            continue
        for item in ranked:
            if item.shape != CandidateShape.FIELD or not isinstance(
                item.candidate, CorrespondenceCandidate
            ):
                continue
            selected.append(
                SelectedStateMapping(
                    source=item.candidate.source,
                    target=item.candidate.target,
                    resolved=resolved,
                )
            )

    source_identity_counts: dict[LogicalStateIdentity, set[EntityRef]] = {}
    for mapping in selected:
        source_identity_counts.setdefault(mapping.source.logical_state, set()).add(mapping.source)
    return tuple(
        replace(
            mapping,
            resolved=(
                mapping.resolved and len(source_identity_counts[mapping.source.logical_state]) == 1
            ),
        )
        for mapping in selected
    )


def infer_function_correspondences(
    source_program: ProgramSemanticModel,
    target_program: ProgramSemanticModel,
    candidate_sets: list[CandidateSet],
    *,
    policy: FunctionCompatibilityPolicy = DEFAULT_COMPATIBILITY_POLICY,
) -> list[FunctionCorrespondenceCandidate]:
    source_signatures = build_function_signatures(source_program)
    target_signatures = build_function_signatures(target_program)
    mappings = select_state_mappings(candidate_sets)
    results: list[FunctionCorrespondenceCandidate] = []

    for source_id, source in source_signatures.items():
        source_states = set(source.state_reads) | set(source.state_writes)
        relevant = tuple(item for item in mappings if item.source.logical_state in source_states)
        if not relevant:
            continue
        mapped_targets = {item.target.logical_state for item in relevant}

        for target_id, target in target_signatures.items():
            target_states = set(target.state_reads) | set(target.state_writes)
            if not (mapped_targets & target_states):
                continue
            mapped_reads = _mapped_pairs(source.state_reads, target.state_reads, relevant)
            mapped_writes = _mapped_pairs(source.state_writes, target.state_writes, relevant)
            effect, details = _effect(source, target, relevant, policy)
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
                    "state_mapping_resolved": all(item.resolved for item in relevant),
                    **details,
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
    source_states: tuple[LogicalStateIdentity, ...],
    target_states: tuple[LogicalStateIdentity, ...],
    mappings: tuple[SelectedStateMapping, ...],
) -> tuple[tuple[EntityRef, EntityRef], ...]:
    sources = set(source_states)
    targets = set(target_states)
    return tuple(
        (item.source, item.target)
        for item in mappings
        if item.source.logical_state in sources and item.target.logical_state in targets
    )


def _effect(
    source: FunctionBehaviorSignature,
    target: FunctionBehaviorSignature,
    mappings: tuple[SelectedStateMapping, ...],
    policy: FunctionCompatibilityPolicy,
) -> tuple[EvidenceEffect, dict[str, object]]:
    mapping_by_state: dict[LogicalStateIdentity, SelectedStateMapping] = {}
    for item in mappings:
        if not item.resolved or item.source.logical_state in mapping_by_state:
            return EvidenceEffect.NEUTRAL, {"reason": "ambiguous_state_mapping"}
        mapping_by_state[item.source.logical_state] = item

    required_states = set(source.state_reads) | set(source.state_writes)
    if not required_states <= mapping_by_state.keys():
        return EvidenceEffect.NEUTRAL, {"reason": "incomplete_state_mapping"}
    if (
        source.resolution != ResolutionStatus.RESOLVED
        or target.resolution != ResolutionStatus.RESOLVED
    ):
        return EvidenceEffect.NEUTRAL, {"reason": "unresolved_signature"}

    expected_reads = {mapping_by_state[state].target.logical_state for state in source.state_reads}
    expected_writes = {
        mapping_by_state[state].target.logical_state for state in source.state_writes
    }
    actual_reads = set(target.state_reads)
    actual_writes = set(target.state_writes)
    required_effects = {
        (effect.kind, mapping_by_state[effect.target].target.logical_state)
        for effect in source.effects
        if effect.target in mapping_by_state
    }
    actual_effects = {(effect.kind, effect.target) for effect in target.effects}
    missing_effects = required_effects - actual_effects
    extra_effects = actual_effects - required_effects
    forbidden_extra_effects = extra_effects - policy.allowed_extra_effects
    allowed_write_targets = {
        target_state for kind, target_state in policy.allowed_extra_effects if kind == "state_write"
    }
    details: dict[str, object] = {
        "required_effects": _effect_keys(required_effects),
        "allowed_extra_effects": _effect_keys(extra_effects & policy.allowed_extra_effects),
        "forbidden_extra_effects": _effect_keys(forbidden_extra_effects),
        "missing_effects": _effect_keys(missing_effects),
        "extra_state_reads": sorted(state.locator for state in actual_reads - expected_reads),
        "allowed_extra_state_writes": sorted(
            state.locator for state in (actual_writes - expected_writes) & allowed_write_targets
        ),
        "forbidden_extra_state_writes": sorted(
            state.locator for state in (actual_writes - expected_writes) - allowed_write_targets
        ),
    }
    compatible = (
        expected_reads == actual_reads
        and expected_writes | allowed_write_targets == actual_writes
        and source.operations == target.operations
        and not missing_effects
        and not forbidden_extra_effects
    )
    return (EvidenceEffect.SUPPORTS if compatible else EvidenceEffect.CONTRADICTS), details


def _effect_keys(
    effects: set[tuple[str, LogicalStateIdentity]] | frozenset[tuple[str, LogicalStateIdentity]],
) -> list[dict[str, str]]:
    return [
        {"kind": kind, "target": target.locator}
        for kind, target in sorted(effects, key=lambda item: (item[0], item[1]))
    ]


def _effects(signature: FunctionBehaviorSignature) -> list[dict[str, str]]:
    return [
        {
            "kind": effect.kind,
            "target": effect.target.locator,
            "owner_function": effect.owner_function,
        }
        for effect in signature.effects
    ]
