from pathlib import Path

import typer

from invariant_cli.analysis.service import analyze_program
from invariant_cli.architecture.loader import load_architecture
from invariant_cli.contracts.model import VerificationObligationKind
from invariant_cli.contracts.storage import (
    load_candidate_contract,
    load_contract_validation,
)
from invariant_cli.gates.architecture import architecture_gates
from invariant_cli.gates.behavior import BehaviorPreservationGate, StateCorrespondenceGate
from invariant_cli.gates.engine import aggregate_verdict, run_gates
from invariant_cli.gates.model import Gate, VerificationContext
from invariant_cli.gates.report import save_gate_report

gate_app = typer.Typer(
    help="Run deterministic translation verification gates.", no_args_is_help=True
)

ContractArgument = typer.Argument(..., help="Candidate translation contract.")
SourceCodeOption = typer.Option(..., "--source-code", help="Source Python file or directory.")
TargetCodeOption = typer.Option(..., "--target-code", help="Target Python file or directory.")
ArchitectureOption = typer.Option(None, "--architecture", help="Target architecture YAML artifact.")
ValidationOption = typer.Option(None, "--validation", help="Held-out validation JSON result.")
OutputOption = typer.Option(None, "--output", help="Write a JSON gate report.")


@gate_app.command("run")
def run_gate_command(
    contract: Path = ContractArgument,
    source_code: Path = SourceCodeOption,
    target_code: Path = TargetCodeOption,
    architecture: Path | None = ArchitectureOption,
    validation: Path | None = ValidationOption,
    output: Path | None = OutputOption,
) -> None:
    candidate_contract = load_candidate_contract(_file(contract, "Contract"))
    architecture_model = (
        None if architecture is None else load_architecture(_file(architecture, "Architecture"))
    )
    validation_result = (
        None if validation is None else load_contract_validation(_file(validation, "Validation"))
    )
    context = VerificationContext(
        contract=candidate_contract,
        source_program=analyze_program(_code_path(source_code, "Source")),
        target_program=analyze_program(_code_path(target_code, "Target")),
        architecture=architecture_model,
        validation=validation_result,
    )

    gates: list[Gate] = [StateCorrespondenceGate()]
    gates.extend(
        BehaviorPreservationGate(
            obligation_id=obligation.id,
            source_locator=obligation.source.locator,
            target_locator=obligation.target.locator,
        )
        for obligation in candidate_contract.obligations
        if obligation.kind == VerificationObligationKind.BEHAVIOR_PRESERVATION
        and obligation.source is not None
        and obligation.target is not None
    )
    gates.extend(architecture_gates(context))
    results = run_gates(gates, context)

    typer.echo("Invariant verification")
    for category in ("state", "behavior", "architecture"):
        selected = [item for item in results if item.category == category]
        if not selected:
            continue
        typer.echo("")
        typer.echo(f"{category.capitalize()} gates")
        for item in selected:
            typer.echo(f"  {item.obligation_id:<36} {item.verdict.value}")
            if item.verdict.value != "PASS":
                typer.echo(f"    {item.message}")
                for evidence in item.evidence:
                    typer.echo(f"    {evidence}")
    overall = aggregate_verdict(results)
    typer.echo("")
    typer.echo("Overall")
    typer.echo(f"  {overall.value}")

    if output is not None:
        saved = save_gate_report(results, output.expanduser().resolve())
        typer.echo(f"Saved: {saved}")


def _file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise typer.BadParameter(f"{label} file not found: {path}")
    return resolved


def _code_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise typer.BadParameter(f"{label} code path not found: {path}")
    return resolved
