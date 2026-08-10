from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    EntityExpression,
    ExecutionPairRef,
    ExpressionCorrespondenceCandidate,
    ExpressionKind,
    Relation,
)
from invariant_cli.contracts.relations import apply_relation, to_decimal
from invariant_cli.matching.model import EntityKind, EntityRef
from invariant_cli.matching.transition import ObservedTransition, flatten_observations
from invariant_cli.observation.model import Observation


class ValidationVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class CorrespondenceValidation:
    source: EntityRef
    target: EntityRef
    verdict: ValidationVerdict
    source_transition: ObservedTransition | None
    target_transition: ObservedTransition | None


@dataclass(frozen=True)
class ExpressionComponentValidation:
    entity: EntityRef
    transition: ObservedTransition | None


@dataclass(frozen=True)
class ExpressionCorrespondenceValidation:
    source: EntityExpression
    target: EntityExpression
    verdict: ValidationVerdict
    source_transition: ObservedTransition | None
    target_transition: ObservedTransition | None
    source_components: list[ExpressionComponentValidation]
    target_components: list[ExpressionComponentValidation]


@dataclass(frozen=True)
class PairValidation:
    pair: ExecutionPairRef
    verdict: ValidationVerdict
    correspondences: list[CorrespondenceValidation]
    expression_correspondences: list[ExpressionCorrespondenceValidation]


@dataclass(frozen=True)
class ContractValidationResult:
    verdict: ValidationVerdict
    pairs: list[PairValidation]


def validate_candidate_contract(
    contract: CandidateTranslationContract,
    pairs: list[
        tuple[
            ExecutionPairRef,
            list[Observation],
            list[Observation],
        ]
    ],
) -> ContractValidationResult:
    pair_results = [
        _validate_pair(
            contract,
            pair_ref,
            source_observations,
            target_observations,
        )
        for pair_ref, source_observations, target_observations in pairs
    ]

    return ContractValidationResult(
        verdict=_aggregate_verdict([result.verdict for result in pair_results]),
        pairs=pair_results,
    )


def _validate_pair(
    contract: CandidateTranslationContract,
    pair_ref: ExecutionPairRef,
    source_observations: list[Observation],
    target_observations: list[Observation],
) -> PairValidation:
    source_values = flatten_observations(source_observations)
    target_values = flatten_observations(target_observations)

    results: list[CorrespondenceValidation] = []

    for candidate in contract.correspondences:
        source_key = _observation_key(candidate.source)
        target_key = _observation_key(candidate.target)

        if source_key is None or target_key is None:
            source_transition = None
            target_transition = None
        else:
            source_transition = source_values.get(source_key)
            target_transition = target_values.get(target_key)

        if source_transition is None or target_transition is None:
            verdict = ValidationVerdict.INCONCLUSIVE
        elif _relation_holds(candidate.relation, source_transition, target_transition):
            verdict = ValidationVerdict.PASS
        else:
            verdict = ValidationVerdict.FAIL

        results.append(
            CorrespondenceValidation(
                source=candidate.source,
                target=candidate.target,
                verdict=verdict,
                source_transition=source_transition,
                target_transition=target_transition,
            )
        )

    expression_results = [
        _validate_expression_correspondence(candidate, source_values, target_values)
        for candidate in contract.expression_correspondences
    ]

    return PairValidation(
        pair=pair_ref,
        verdict=_aggregate_verdict(
            [result.verdict for result in results]
            + [result.verdict for result in expression_results]
        ),
        correspondences=results,
        expression_correspondences=expression_results,
    )


def _validate_expression_correspondence(
    candidate: ExpressionCorrespondenceCandidate,
    source_values: dict[tuple[str, str, str], ObservedTransition],
    target_values: dict[tuple[str, str, str], ObservedTransition],
) -> ExpressionCorrespondenceValidation:
    source_transition, source_components = _evaluate_expression(candidate.source, source_values)
    target_transition, target_components = _evaluate_expression(candidate.target, target_values)

    if source_transition is None or target_transition is None:
        verdict = ValidationVerdict.INCONCLUSIVE
    elif _relation_holds(candidate.relation, source_transition, target_transition):
        verdict = ValidationVerdict.PASS
    else:
        verdict = ValidationVerdict.FAIL

    return ExpressionCorrespondenceValidation(
        source=candidate.source,
        target=candidate.target,
        verdict=verdict,
        source_transition=source_transition,
        target_transition=target_transition,
        source_components=source_components,
        target_components=target_components,
    )


def _evaluate_expression(
    expression: EntityExpression,
    values: dict[tuple[str, str, str], ObservedTransition],
) -> tuple[ObservedTransition | None, list[ExpressionComponentValidation]]:
    components = [
        ExpressionComponentValidation(
            entity=entity,
            transition=(values.get(key) if (key := _observation_key(entity)) is not None else None),
        )
        for entity in expression.components
    ]
    transitions = [component.transition for component in components]
    if any(transition is None for transition in transitions):
        return None, components

    typed_transitions = [transition for transition in transitions if transition is not None]
    if expression.kind == ExpressionKind.IDENTITY:
        return typed_transitions[0], components

    if expression.kind == ExpressionKind.SUM:
        before = _sum_numeric([transition.before for transition in typed_transitions])
        after = _sum_numeric([transition.after for transition in typed_transitions])
        if before is None or after is None:
            return None, components
        return ObservedTransition(before=before, after=after), components

    raise ValueError(f"Unsupported expression kind: {expression.kind}")


def _sum_numeric(values: list[Any]) -> Decimal | None:
    numbers = [to_decimal(value) for value in values]
    if any(number is None for number in numbers):
        return None
    return sum((number for number in numbers if number is not None), start=Decimal(0))


def _aggregate_verdict(verdicts: list[ValidationVerdict]) -> ValidationVerdict:
    if not verdicts:
        return ValidationVerdict.INCONCLUSIVE
    if ValidationVerdict.FAIL in verdicts:
        return ValidationVerdict.FAIL
    if ValidationVerdict.INCONCLUSIVE in verdicts:
        return ValidationVerdict.INCONCLUSIVE
    return ValidationVerdict.PASS


def _observation_key(entity: EntityRef) -> tuple[str, str, str] | None:
    observation_kinds = {
        EntityKind.JSON_FIELD: "json",
        EntityKind.SQLITE_FIELD: "sqlite",
    }
    observation_kind = observation_kinds.get(entity.kind)

    if observation_kind is None:
        return None
    return (observation_kind, entity.namespace, entity.identifier)


def _relation_holds(
    relation: Relation,
    source: ObservedTransition,
    target: ObservedTransition,
) -> bool:
    transformed_before = apply_relation(relation, source.before)
    transformed_after = apply_relation(relation, source.after)

    return _values_match(transformed_before, target.before) and _values_match(
        transformed_after, target.after
    )


def _values_match(left: Any, right: Any) -> bool:
    if isinstance(left, Decimal):
        right_decimal = to_decimal(right)
        return right_decimal is not None and bool(left == right_decimal)

    return bool(left == right)
