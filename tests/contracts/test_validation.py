from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    CorrespondenceCandidate,
    DynamicEvidence,
    ExecutionPairRef,
    ObservationSelector,
)
from invariant_cli.contracts.validation import (
    ValidationVerdict,
    validate_candidate_contract,
)
from invariant_cli.observation.model import (
    Observation,
    ValueChange,
)


def observation(
    resource: str,
    path: str,
    before: object,
    after: object,
) -> Observation:
    return Observation(
        source=resource,
        kind="json",
        changes=[
            ValueChange(
                path=path,
                before=before,
                after=after,
            )
        ],
    )


def contract() -> CandidateTranslationContract:
    return CandidateTranslationContract(
        version=1,
        paired_executions=[
            ExecutionPairRef(
                source_execution="source-1",
                target_execution="target-1",
            ),
            ExecutionPairRef(
                source_execution="source-2",
                target_execution="target-2",
            ),
            ExecutionPairRef(
                source_execution="source-3",
                target_execution="target-3",
            ),
        ],
        correspondences=[
            CorrespondenceCandidate(
                source=ObservationSelector(
                    resource=("experiments/translation_contract_demo/source/state.json"),
                    path="balance",
                ),
                target=ObservationSelector(
                    resource=("experiments/translation_contract_demo/target/account.json"),
                    path="remaining",
                ),
                evidence=DynamicEvidence(
                    matched_pairs=3,
                    total_pairs=3,
                    distinct_transitions=3,
                ),
            )
        ],
    )


def test_validation_passes_on_held_out_pair() -> None:
    result = validate_candidate_contract(
        contract(),
        [
            (
                ExecutionPairRef(
                    source_execution="source-4",
                    target_execution="target-4",
                ),
                [
                    observation(
                        "experiments/translation_contract_demo/source/state.json",
                        "balance",
                        300,
                        225,
                    )
                ],
                [
                    observation(
                        "experiments/translation_contract_demo/target/account.json",
                        "remaining",
                        300,
                        225,
                    )
                ],
            )
        ],
    )

    assert result.verdict == ValidationVerdict.PASS


def test_validation_fails_on_divergence() -> None:
    result = validate_candidate_contract(
        contract(),
        [
            (
                ExecutionPairRef(
                    source_execution="source-4",
                    target_execution="target-4",
                ),
                [
                    observation(
                        "experiments/translation_contract_demo/source/state.json",
                        "balance",
                        300,
                        225,
                    )
                ],
                [
                    observation(
                        "experiments/translation_contract_demo/target/account.json",
                        "remaining",
                        300,
                        230,
                    )
                ],
            )
        ],
    )

    assert result.verdict == ValidationVerdict.FAIL


def test_validation_is_inconclusive_when_observation_missing() -> None:
    result = validate_candidate_contract(
        contract(),
        [
            (
                ExecutionPairRef(
                    source_execution="source-4",
                    target_execution="target-4",
                ),
                [
                    observation(
                        "experiments/translation_contract_demo/source/state.json",
                        "balance",
                        300,
                        225,
                    )
                ],
                [],
            )
        ],
    )

    assert result.verdict == ValidationVerdict.INCONCLUSIVE
