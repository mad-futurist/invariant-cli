from pathlib import Path

from invariant_cli.analysis.service import analyze_program
from invariant_cli.architecture.loader import load_architecture
from invariant_cli.contracts.model import ArchitectureArtifactRef, CandidateTranslationContract
from invariant_cli.gates.architecture import architecture_gates
from invariant_cli.gates.engine import run_gates
from invariant_cli.gates.model import GateVerdict, VerificationContext


def test_changed_architecture_artifact_is_inconclusive(tmp_path: Path) -> None:
    architecture_path = tmp_path / "invariant.arch.yaml"
    architecture_path.write_text(
        """version: 1
components:
  - id: service
    modules: [app]
rules:
  - id: no-write
    kind: forbid_state_write
    component: service
""",
        encoding="utf-8",
    )
    original = load_architecture(architecture_path)
    architecture_path.write_text(
        architecture_path.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )
    changed = load_architecture(architecture_path)
    code = tmp_path / "app.py"
    code.write_text("def run():\n    return None\n", encoding="utf-8")
    program = analyze_program(code)
    context = VerificationContext(
        contract=CandidateTranslationContract(
            version=7,
            paired_executions=[],
            correspondences=[],
            architecture=ArchitectureArtifactRef(
                original.artifact_path, original.version, original.sha256
            ),
        ),
        source_program=program,
        target_program=program,
        architecture=changed,
    )

    results = run_gates(architecture_gates(context), context)

    assert len(results) == 1
    assert results[0].gate_id == "architecture-artifact-binding"
    assert results[0].verdict == GateVerdict.INCONCLUSIVE
    assert "changed" in results[0].message


def test_state_ownership_matches_full_logical_state_identity(tmp_path: Path) -> None:
    architecture_path = tmp_path / "invariant.arch.yaml"
    architecture_path.write_text(
        """version: 1
components:
  - id: service
    modules: [payment]
  - id: persistence
    modules: [repository]
rules:
  - id: account-owner
    kind: state_write_owner
    component: persistence
    state: [account.remaining]
""",
        encoding="utf-8",
    )
    architecture = load_architecture(architecture_path)
    code = tmp_path / "code"
    code.mkdir()
    (code / "payment.py").write_text(
        'def record(value):\n    audit["remaining"] = value\n', encoding="utf-8"
    )
    (code / "repository.py").write_text(
        'def store(value):\n    account["remaining"] = value\n', encoding="utf-8"
    )
    program = analyze_program(code)
    context = VerificationContext(
        contract=CandidateTranslationContract(
            version=7,
            paired_executions=[],
            correspondences=[],
            architecture=ArchitectureArtifactRef(
                architecture.artifact_path, architecture.version, architecture.sha256
            ),
        ),
        source_program=program,
        target_program=program,
        architecture=architecture,
    )

    results = run_gates(architecture_gates(context), context)

    owner_result = next(item for item in results if item.obligation_id == "account-owner")
    assert owner_result.verdict == GateVerdict.PASS
