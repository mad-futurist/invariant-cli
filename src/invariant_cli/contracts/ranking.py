from collections.abc import Iterable

from invariant_cli.contracts.model import (
    CandidateHypothesis,
    CandidateSet,
    CandidateSetStatus,
    CandidateShape,
    CorrespondenceCandidate,
    ExpressionCorrespondenceCandidate,
    ExpressionKind,
    RankedCandidate,
)
from invariant_cli.matching.model import EntityRef, Evidence, EvidenceKind
from invariant_cli.matching.schema.observed import entity_ref
from invariant_cli.matching.transition import flatten_observations
from invariant_cli.observation.model import Observation

AMBIGUITY_MARGIN = 5
DYNAMIC_BASE = 100
MATCHED_PAIR_WEIGHT = 5
DISTINCT_TRANSITION_WEIGHT = 2
SCHEMA_TYPE_WEIGHT = 30
SCHEMA_NULLABILITY_WEIGHT = 5
SCHEMA_PRIMARY_KEY_WEIGHT = 3
SCHEMA_SCOPE_WEIGHT = 5
SCHEMA_NAME_TOKEN_WEIGHT = 4
STATIC_OPERATION_WEIGHT = 10
EXPRESSION_COMPLEXITY_COST = 5


def source_entities_from_pairs(
    pairs: list[tuple[list[Observation], list[Observation]]],
) -> list[EntityRef]:
    entities = {
        entity
        for source_observations, _ in pairs
        for key in flatten_observations(source_observations)
        if (entity := entity_ref(key)) is not None
    }
    return sorted(entities, key=_entity_key)


def build_candidate_sets(
    correspondences: list[CorrespondenceCandidate],
    expression_correspondences: list[ExpressionCorrespondenceCandidate],
    *,
    sources: Iterable[EntityRef] = (),
) -> list[CandidateSet]:
    grouped: dict[EntityRef, list[tuple[CandidateShape, CandidateHypothesis]]] = {
        source: [] for source in sources
    }

    for field_candidate in correspondences:
        grouped.setdefault(field_candidate.source, []).append(
            (CandidateShape.FIELD, field_candidate)
        )

    for expression_candidate in expression_correspondences:
        source = _expression_source(expression_candidate)
        if source is not None:
            grouped.setdefault(source, []).append((CandidateShape.EXPRESSION, expression_candidate))

    return [
        _rank_set(source, hypotheses)
        for source, hypotheses in sorted(grouped.items(), key=lambda item: _entity_key(item[0]))
    ]


def _rank_set(
    source: EntityRef,
    hypotheses: list[tuple[CandidateShape, CandidateHypothesis]],
) -> CandidateSet:
    if not hypotheses:
        return CandidateSet(source=source, status=CandidateSetStatus.REJECTED)

    scored = [
        (shape, candidate, _ranking_factors(shape, candidate)) for shape, candidate in hypotheses
    ]
    scored.sort(
        key=lambda item: (
            -sum(item[2].values()),
            item[0].value,
            _target_key(item[1]),
        )
    )

    ranked: list[RankedCandidate] = []
    previous_score: int | None = None
    rank = 0
    for shape, candidate, factors in scored:
        score = sum(factors.values())
        if score != previous_score:
            rank += 1
            previous_score = score
        ranked.append(
            RankedCandidate(
                shape=shape,
                rank=rank,
                score=score,
                factors=factors,
                candidate=candidate,
            )
        )

    top = ranked[0]
    close_alternative = len(ranked) > 1 and top.score - ranked[1].score <= AMBIGUITY_MARGIN
    evidence_kinds = {item.kind for item in top.candidate.evidence}

    if close_alternative:
        status = CandidateSetStatus.AMBIGUOUS
    elif len(evidence_kinds) < 2:
        status = CandidateSetStatus.INSUFFICIENT_EVIDENCE
    else:
        status = CandidateSetStatus.CONFIDENT_CANDIDATE

    return CandidateSet(source=source, status=status, candidates=ranked)


def _ranking_factors(
    shape: CandidateShape,
    candidate: CandidateHypothesis,
) -> dict[str, int]:
    factors = {
        "dynamic": _dynamic_score(candidate.evidence),
        "schema": _schema_score(candidate.evidence),
        "static": _static_score(candidate.evidence),
        "complexity": -EXPRESSION_COMPLEXITY_COST if shape == CandidateShape.EXPRESSION else 0,
    }
    return factors


def _dynamic_score(evidence: list[Evidence]) -> int:
    item = _evidence(evidence, EvidenceKind.DYNAMIC_TRANSITION)
    if item is None:
        return 0
    matched_pairs = _int_attribute(item, "matched_pairs")
    distinct_transitions = _int_attribute(item, "distinct_transitions")
    return (
        DYNAMIC_BASE
        + min(matched_pairs, 10) * MATCHED_PAIR_WEIGHT
        + min(distinct_transitions, 10) * DISTINCT_TRANSITION_WEIGHT
    )


def _schema_score(evidence: list[Evidence]) -> int:
    item = _evidence(evidence, EvidenceKind.SCHEMA)
    if item is None:
        return 0

    score = 0
    if item.attributes.get("type_compatible") is True:
        score += SCHEMA_TYPE_WEIGHT
    if item.attributes.get("source_nullable") == item.attributes.get("target_nullable"):
        score += SCHEMA_NULLABILITY_WEIGHT
    if item.attributes.get("source_primary_key_context") == item.attributes.get(
        "target_primary_key_context"
    ):
        score += SCHEMA_PRIMARY_KEY_WEIGHT
    if item.attributes.get("structural_scope_compatible") is True:
        score += SCHEMA_SCOPE_WEIGHT
    common_tokens = item.attributes.get("common_name_tokens")
    if isinstance(common_tokens, list):
        score += min(len(common_tokens), 5) * SCHEMA_NAME_TOKEN_WEIGHT
    return score


def _static_score(evidence: list[Evidence]) -> int:
    item = _evidence(evidence, EvidenceKind.STATIC_USAGE)
    if item is None:
        return 0
    common_operations = item.attributes.get("common_operations")
    if not isinstance(common_operations, list):
        return 0
    return min(len(common_operations), 5) * STATIC_OPERATION_WEIGHT


def _evidence(evidence: list[Evidence], kind: EvidenceKind) -> Evidence | None:
    return next((item for item in evidence if item.kind == kind), None)


def _int_attribute(evidence: Evidence, name: str) -> int:
    value = evidence.attributes.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _expression_source(candidate: ExpressionCorrespondenceCandidate) -> EntityRef | None:
    if candidate.source.kind != ExpressionKind.IDENTITY:
        return None
    return candidate.source.components[0]


def _target_key(candidate: CandidateHypothesis) -> tuple[object, ...]:
    targets: tuple[str, ...]
    if isinstance(candidate, CorrespondenceCandidate):
        targets = (candidate.target.locator,)
    else:
        targets = tuple(component.locator for component in candidate.target.components)
    return (
        targets,
        candidate.relation.kind.value,
        candidate.relation.scale,
        candidate.relation.offset,
    )


def _entity_key(entity: EntityRef) -> tuple[str, str, str]:
    return (entity.kind.value, entity.namespace, entity.identifier)
