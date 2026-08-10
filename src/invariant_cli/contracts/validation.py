from dataclasses import dataclass
from enum import StrEnum

from invariant_cli.contracts.inference import (
    ObservedTransition,
    flatten_observations,
    transitions_equal,
)
from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    ExecutionPairRef,
    ObservationSelector,
)
from invariant_cli.observation.model import Observation


class ValidationVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class CorrespondenceValidation:
    source: ObservationSelector
    target: ObservationSelector
    verdict: ValidationVerdict
    source_transition: ObservedTransition | None
    target_transition: ObservedTransition | None


@dataclass(frozen=True)
class PairValidation:
    pair: ExecutionPairRef
    verdict: ValidationVerdict
    correspondences: list[CorrespondenceValidation]


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
        source_key = (candidate.source.resource, candidate.source.path)
        target_key = (candidate.target.resource, candidate.target.path)

        source_transition = source_values.get(source_key)
        target_transition = target_values.get(target_key)

        if source_transition is None or target_transition is None:
            verdict = ValidationVerdict.INCONCLUSIVE
        elif transitions_equal(source_transition, target_transition):
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

    return PairValidation(
        pair=pair_ref,
        verdict=_aggregate_verdict([result.verdict for result in results]),
        correspondences=results,
    )


def _aggregate_verdict(verdicts: list[ValidationVerdict]) -> ValidationVerdict:
    if not verdicts:
        return ValidationVerdict.INCONCLUSIVE
    if ValidationVerdict.FAIL in verdicts:
        return ValidationVerdict.FAIL
    if ValidationVerdict.INCONCLUSIVE in verdicts:
        return ValidationVerdict.INCONCLUSIVE
    return ValidationVerdict.PASS
