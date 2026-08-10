from invariant_cli.contracts.expression_inference import infer_expression_correspondences
from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    ExecutionPairRef,
    ExpressionKind,
    RelationKind,
)
from invariant_cli.contracts.validation import ValidationVerdict, validate_candidate_contract
from invariant_cli.observation.model import Observation, ValueChange


def _source(before: int, after: int) -> list[Observation]:
    return [
        Observation(
            source="source/legacy.db",
            kind="sqlite",
            changes=[ValueChange("wallets[id=1].balance_cents", before, after)],
        )
    ]


def _target(
    principal_before: int,
    principal_after: int,
    reserve_before: int,
    reserve_after: int,
) -> list[Observation]:
    return [
        Observation(
            source="target/account.json",
            kind="json",
            changes=[
                ValueChange("principal_eur", principal_before, principal_after),
                ValueChange("reserve_eur", reserve_before, reserve_after),
            ],
        )
    ]


def _training_pairs() -> list[tuple[list[Observation], list[Observation]]]:
    return [
        (_source(10000, 7000), _target(80, 55, 20, 15)),
        (_source(10000, 4000), _target(70, 20, 30, 20)),
        (_source(25000, 19000), _target(100, 70, 150, 120)),
    ]


def test_infers_source_to_sum_of_two_targets() -> None:
    candidates = infer_expression_correspondences(_training_pairs())

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source.kind == ExpressionKind.IDENTITY
    assert candidate.source.components[0].identifier == "wallets[id=1].balance_cents"
    assert candidate.target.kind == ExpressionKind.SUM
    assert [component.identifier for component in candidate.target.components] == [
        "principal_eur",
        "reserve_eur",
    ]
    assert candidate.relation.kind == RelationKind.AFFINE
    assert candidate.relation.scale == "0.01"


def test_validates_sum_and_preserves_component_counterexample() -> None:
    candidate = infer_expression_correspondences(_training_pairs())[0]
    contract = CandidateTranslationContract(
        version=3,
        paired_executions=[],
        correspondences=[],
        expression_correspondences=[candidate],
    )
    pair = ExecutionPairRef("held-out-source", "held-out-target")

    passing = validate_candidate_contract(
        contract,
        [(pair, _source(30000, 22500), _target(110, 90, 190, 135))],
    )
    assert passing.verdict == ValidationVerdict.PASS

    failing = validate_candidate_contract(
        contract,
        [(pair, _source(30000, 22500), _target(110, 90, 190, 140))],
    )
    result = failing.pairs[0].expression_correspondences[0]
    assert failing.verdict == ValidationVerdict.FAIL
    assert result.target_transition is not None
    assert result.target_transition.after == 230
    assert [
        component.transition.after for component in result.target_components if component.transition
    ] == [
        90,
        140,
    ]
