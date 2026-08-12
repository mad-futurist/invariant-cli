from pathlib import Path

import pytest

from invariant_cli.analysis.service import analyze_program
from invariant_cli.architecture.loader import load_architecture
from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    CorrespondenceCandidate,
    FunctionCorrespondenceStatus,
    Relation,
    RelationKind,
)
from invariant_cli.contracts.validation import ContractValidationResult, ValidationVerdict
from invariant_cli.gates.architecture import architecture_gates
from invariant_cli.gates.behavior import BehaviorPreservationGate
from invariant_cli.gates.engine import aggregate_verdict, run_gates
from invariant_cli.gates.model import GateVerdict, VerificationContext
from invariant_cli.matching.model import EntityKind, EntityRef

ROOT = Path(__file__).parents[2] / "experiments" / "verified_migration_demo"
SOURCE_FUNCTION = "service#pay"
TARGET_FUNCTION = "payment#process"


def _context(target: str, validation: ValidationVerdict) -> VerificationContext:
    source_field = EntityRef(EntityKind.JSON_FIELD, "source/state.json", "balance_cents")
    target_field = EntityRef(EntityKind.JSON_FIELD, "target/account.json", "remaining_eur")
    field_candidate = CorrespondenceCandidate(
        source=source_field,
        target=target_field,
        relation=Relation(RelationKind.AFFINE, scale="0.01"),
        evidence=[],
    )
    source_program = analyze_program(ROOT / "source")
    target_program = analyze_program(ROOT / target)
    function_candidates = infer_function_correspondences(
        source_program, target_program, [field_candidate]
    )
    contract = CandidateTranslationContract(
        version=7,
        paired_executions=[],
        correspondences=[field_candidate],
        function_correspondences=function_candidates,
    )
    return VerificationContext(
        contract=contract,
        source_program=source_program,
        target_program=target_program,
        architecture=load_architecture(ROOT / "invariant.arch.yaml"),
        validation=ContractValidationResult(validation, []),
    )


@pytest.mark.parametrize(
    ("target", "validation", "behavior", "architecture", "overall"),
    [
        ("target", ValidationVerdict.PASS, GateVerdict.PASS, GateVerdict.PASS, GateVerdict.PASS),
        (
            "target_bad_arch",
            ValidationVerdict.PASS,
            GateVerdict.PASS,
            GateVerdict.FAIL,
            GateVerdict.FAIL,
        ),
        (
            "target_bad_behavior",
            ValidationVerdict.FAIL,
            GateVerdict.FAIL,
            GateVerdict.PASS,
            GateVerdict.FAIL,
        ),
    ],
)
def test_verified_migration_variants(
    target: str,
    validation: ValidationVerdict,
    behavior: GateVerdict,
    architecture: GateVerdict,
    overall: GateVerdict,
) -> None:
    context = _context(target, validation)
    candidate = next(
        item
        for item in context.contract.function_correspondences
        if item.source.locator == SOURCE_FUNCTION and item.target.locator == TARGET_FUNCTION
    )
    expected_status = (
        FunctionCorrespondenceStatus.REJECTED
        if target == "target_bad_behavior"
        else FunctionCorrespondenceStatus.CANDIDATE
    )
    assert candidate.status == expected_status

    behavior_result = BehaviorPreservationGate(
        "preserve-pay", SOURCE_FUNCTION, TARGET_FUNCTION
    ).evaluate(context)
    architecture_results = run_gates(architecture_gates(context), context)

    assert behavior_result.verdict == behavior
    assert aggregate_verdict(architecture_results) == architecture
    assert aggregate_verdict([behavior_result, *architecture_results]) == overall
