import json
from pathlib import Path

from typer.testing import CliRunner

from invariant_cli.analysis.service import analyze_program
from invariant_cli.architecture.loader import load_architecture
from invariant_cli.cli import app
from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.model import (
    ArchitectureArtifactRef,
    CandidateSet,
    CandidateSetStatus,
    CandidateShape,
    CandidateTranslationContract,
    CorrespondenceCandidate,
    ExecutionPairRef,
    RankedCandidate,
    Relation,
    RelationKind,
    VerificationObligation,
    VerificationObligationKind,
)
from invariant_cli.contracts.storage import save_candidate_contract, save_contract_validation
from invariant_cli.contracts.validation import (
    ContractValidationResult,
    CorrespondenceValidation,
    PairValidation,
    ValidationVerdict,
)
from invariant_cli.matching.model import EntityKind, EntityRef

runner = CliRunner()
ROOT = Path(__file__).parents[2] / "experiments" / "verified_migration_demo"


def test_gate_run_reports_all_gate_groups(tmp_path: Path) -> None:
    source_field = EntityRef(EntityKind.JSON_FIELD, "source/state.json", "balance_cents")
    target_field = EntityRef(EntityKind.JSON_FIELD, "target/account.json", "remaining_eur")
    field_candidate = CorrespondenceCandidate(
        source=source_field,
        target=target_field,
        relation=Relation(RelationKind.AFFINE, scale="0.01"),
        evidence=[],
    )
    source_program = analyze_program(ROOT / "source")
    target_program = analyze_program(ROOT / "target")
    candidate_sets = [
        CandidateSet(
            source=source_field,
            status=CandidateSetStatus.WELL_SUPPORTED_CANDIDATE,
            candidates=[RankedCandidate(CandidateShape.FIELD, 1, 100, {}, field_candidate)],
        )
    ]
    functions = infer_function_correspondences(source_program, target_program, candidate_sets)
    translated = next(
        item
        for item in functions
        if item.source.locator == "service#pay" and item.target.locator == "payment#process"
    )
    architecture = load_architecture(ROOT / "invariant.arch.yaml")
    contract = CandidateTranslationContract(
        version=7,
        paired_executions=[],
        correspondences=[field_candidate],
        candidate_sets=candidate_sets,
        function_correspondences=functions,
        obligations=[
            VerificationObligation(
                id="preserve-pay",
                kind=VerificationObligationKind.BEHAVIOR_PRESERVATION,
                source=translated.source,
                target=translated.target,
            )
        ],
        architecture=ArchitectureArtifactRef(
            architecture.artifact_path, architecture.version, architecture.sha256
        ),
    )
    contract_path = save_candidate_contract(contract, directory=tmp_path)
    validation_path = save_contract_validation(
        ContractValidationResult(
            ValidationVerdict.PASS,
            [
                PairValidation(
                    pair=ExecutionPairRef("held-out-source", "held-out-target"),
                    verdict=ValidationVerdict.PASS,
                    correspondences=[
                        CorrespondenceValidation(
                            source_field,
                            target_field,
                            ValidationVerdict.PASS,
                            None,
                            None,
                        )
                    ],
                    expression_correspondences=[],
                )
            ],
        ),
        contract=contract,
        directory=tmp_path,
        contract_path=contract_path,
    )
    report_path = tmp_path / "gate-report.json"

    result = runner.invoke(
        app,
        [
            "gate",
            "run",
            str(contract_path),
            "--source-code",
            str(ROOT / "source"),
            "--target-code",
            str(ROOT / "target"),
            "--architecture",
            str(ROOT / "invariant.arch.yaml"),
            "--validation",
            str(validation_path),
            "--output",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "State gates" in result.stdout
    assert "Behavior gates" in result.stdout
    assert "Architecture gates" in result.stdout
    assert "Overall\n  PASS" in result.stdout
    assert json.loads(report_path.read_text(encoding="utf-8"))["overall"] == "PASS"
