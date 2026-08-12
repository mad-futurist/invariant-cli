from pathlib import Path

from invariant_cli.analysis.service import analyze_program
from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.model import (
    CandidateSet,
    CandidateSetStatus,
    CandidateShape,
    CandidateTranslationContract,
    CorrespondenceCandidate,
    ExecutionPairRef,
    RankedCandidate,
    Relation,
    RelationKind,
)
from invariant_cli.contracts.validation import (
    ContractValidationResult,
    CorrespondenceValidation,
    PairValidation,
    ValidationVerdict,
)
from invariant_cli.gates.behavior import BehaviorPreservationGate
from invariant_cli.gates.model import GateVerdict, VerificationContext
from invariant_cli.matching.model import EntityKind, EntityRef


def test_behavior_gate_scopes_held_out_validation_to_mapped_function_state(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.py"
    source_path.write_text('def pay(value):\n    state["balance"] -= value\n', encoding="utf-8")
    target_path = tmp_path / "target.py"
    target_path.write_text(
        'def process(value):\n    account["remaining"] -= value\n', encoding="utf-8"
    )
    source_state = EntityRef(EntityKind.JSON_FIELD, "state.json", "balance")
    target_state = EntityRef(EntityKind.JSON_FIELD, "account.json", "remaining")
    state_candidate = CorrespondenceCandidate(
        source_state, target_state, Relation(RelationKind.EXACT), []
    )
    candidate_sets = [
        CandidateSet(
            source_state,
            CandidateSetStatus.WELL_SUPPORTED_CANDIDATE,
            [RankedCandidate(CandidateShape.FIELD, 1, 100, {}, state_candidate)],
        )
    ]
    source_program = analyze_program(source_path)
    target_program = analyze_program(target_path)
    functions = infer_function_correspondences(source_program, target_program, candidate_sets)
    unrelated_source = EntityRef(EntityKind.JSON_FIELD, "profile.json", "status")
    unrelated_target = EntityRef(EntityKind.JSON_FIELD, "user.json", "state")
    validation = ContractValidationResult(
        ValidationVerdict.FAIL,
        [
            PairValidation(
                ExecutionPairRef("source-held-out", "target-held-out"),
                ValidationVerdict.FAIL,
                [
                    CorrespondenceValidation(
                        source_state,
                        target_state,
                        ValidationVerdict.PASS,
                        None,
                        None,
                    ),
                    CorrespondenceValidation(
                        unrelated_source,
                        unrelated_target,
                        ValidationVerdict.FAIL,
                        None,
                        None,
                    ),
                ],
                [],
            )
        ],
    )
    context = VerificationContext(
        contract=CandidateTranslationContract(
            version=7,
            paired_executions=[],
            correspondences=[state_candidate],
            candidate_sets=candidate_sets,
            function_correspondences=functions,
        ),
        source_program=source_program,
        target_program=target_program,
        validation=validation,
    )

    result = BehaviorPreservationGate("preserve-pay", "source#pay", "target#process").evaluate(
        context
    )

    assert result.verdict == GateVerdict.PASS
