from pathlib import Path

import typer

from invariant_cli.contracts.enrichment import enrich_with_static_usage
from invariant_cli.contracts.expression_inference import infer_expression_correspondences
from invariant_cli.contracts.inference import infer_correspondences
from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    EntityExpression,
    ExecutionPairRef,
)
from invariant_cli.contracts.storage import (
    load_candidate_contract,
    save_candidate_contract,
    save_contract_validation,
)
from invariant_cli.contracts.validation import validate_candidate_contract
from invariant_cli.execution.reader import load_execution_observations
from invariant_cli.matching.model import EvidenceKind
from invariant_cli.matching.static.model import FieldUsage
from invariant_cli.matching.static.python_ast import extract_field_usage
from invariant_cli.workspace.model import WorkspacePaths
from invariant_cli.workspace.service import (
    get_workspace_paths,
    load_workspace_paths,
)

contract_app = typer.Typer(
    help="Infer and manage translation contracts.",
    no_args_is_help=True,
)


PairOption = typer.Option(
    ...,
    "--pair",
    help=(
        "Paired source and target execution IDs "
        "in SOURCE:TARGET format. "
        "Pass this option multiple times."
    ),
)


WorkspaceRootOption = typer.Option(
    None,
    "--workspace-root",
    "-w",
    help="Path to the project root containing .invariant.",
)


SourceCodeOption = typer.Option(
    None,
    "--source-code",
    help="Python source file used to add static usage evidence.",
)


TargetCodeOption = typer.Option(
    None,
    "--target-code",
    help="Python target file used to add static usage evidence.",
)


@contract_app.command("infer")
def infer_contract(
    pair: list[str] = PairOption,
    workspace_root: Path | None = WorkspaceRootOption,
    source_code: Path | None = SourceCodeOption,
    target_code: Path | None = TargetCodeOption,
) -> None:
    workspace = _resolve_workspace(
        workspace_root,
    )

    if len(pair) < 3:
        raise typer.BadParameter("Contract inference requires at least 3 paired executions.")

    if (source_code is None) != (target_code is None):
        raise typer.BadParameter("Pass --source-code and --target-code together.")

    pair_refs: list[ExecutionPairRef] = []

    observation_pairs = []

    for raw_pair in pair:
        source_id, target_id = _parse_pair(raw_pair)

        source_path = workspace.executions / f"{source_id}.json"

        target_path = workspace.executions / f"{target_id}.json"

        if not source_path.exists():
            raise typer.BadParameter(f"Source execution not found: {source_id}")

        if not target_path.exists():
            raise typer.BadParameter(f"Target execution not found: {target_id}")

        source_observations = load_execution_observations(source_path)

        target_observations = load_execution_observations(target_path)

        pair_refs.append(
            ExecutionPairRef(
                source_execution=source_id,
                target_execution=target_id,
            )
        )

        observation_pairs.append(
            (
                source_observations,
                target_observations,
            )
        )

    candidates = infer_correspondences(observation_pairs)
    expression_candidates = infer_expression_correspondences(observation_pairs)

    if source_code is not None and target_code is not None:
        candidates = enrich_with_static_usage(
            candidates,
            _extract_python_usage(source_code, label="source"),
            _extract_python_usage(target_code, label="target"),
        )

    contract = CandidateTranslationContract(
        version=3,
        paired_executions=pair_refs,
        correspondences=candidates,
        expression_correspondences=expression_candidates,
    )

    output_path = save_candidate_contract(
        contract,
        directory=workspace.contracts,
    )

    typer.echo(f"Paired executions: {len(pair_refs)}")

    typer.echo(f"Candidate correspondences: {len(candidates)}")
    typer.echo(f"Expression correspondences: {len(expression_candidates)}")

    if candidates:
        typer.echo("")

        for candidate in candidates:
            typer.echo(candidate.source.locator)
            typer.echo("  <->")
            typer.echo(candidate.target.locator)
            dyn = next(
                (e for e in candidate.evidence if e.kind == EvidenceKind.DYNAMIC_TRANSITION),
                None,
            )
            if dyn:
                typer.echo(
                    f"  dynamic evidence: "
                    f"{dyn.attributes['matched_pairs']}/"
                    f"{dyn.attributes['total_pairs']}"
                )
                typer.echo(f"  distinct transitions: {dyn.attributes['distinct_transitions']}")

            static = next(
                (e for e in candidate.evidence if e.kind == EvidenceKind.STATIC_USAGE),
                None,
            )
            if static:
                common_operations = static.attributes.get("common_operations", [])
                if isinstance(common_operations, list):
                    operations = ", ".join(str(operation) for operation in common_operations)
                    typer.echo(f"  static evidence: {operations}")
            typer.echo("")
    if expression_candidates:
        for expression_candidate in expression_candidates:
            typer.echo(_expression_label(expression_candidate.source))
            typer.echo("  <->")
            typer.echo(_expression_label(expression_candidate.target))
            typer.echo(
                f"  relation: {expression_candidate.relation.kind.value} "
                f"(scale={expression_candidate.relation.scale}, "
                f"offset={expression_candidate.relation.offset})"
            )
            typer.echo("")

    if not candidates and not expression_candidates:
        typer.echo("No correspondence candidates found.")

    typer.echo(f"Saved: {output_path}")


def _parse_pair(
    value: str,
) -> tuple[str, str]:
    source_id, separator, target_id = value.partition(":")

    if not separator or not source_id.strip() or not target_id.strip():
        raise typer.BadParameter(f"Invalid pair '{value}'. Expected SOURCE:TARGET.")

    return (
        source_id.strip(),
        target_id.strip(),
    )


def _extract_python_usage(path: Path, *, label: str) -> dict[str, FieldUsage]:
    resolved = path.expanduser().resolve()

    if not resolved.is_file():
        raise typer.BadParameter(f"{label.capitalize()} code file not found: {path}")

    try:
        return extract_field_usage(resolved)
    except (OSError, SyntaxError) as exc:
        raise typer.BadParameter(f"Could not analyze {label} code: {exc}") from exc


def _resolve_workspace(
    workspace_root: Path | None,
) -> WorkspacePaths:
    if workspace_root is None:
        try:
            return load_workspace_paths(Path.cwd())
        except FileNotFoundError as exc:
            raise typer.BadParameter(
                "No Invariant workspace found. Run 'invariant init' first or pass --workspace-root."
            ) from exc

    root = workspace_root.expanduser().resolve()

    if not (root / ".invariant").is_dir():
        raise typer.BadParameter(f"{root} does not contain a .invariant directory.")

    return get_workspace_paths(root)


ContractArgument = typer.Argument(
    ...,
    help="Candidate contract file.",
)


@contract_app.command("validate")
def validate_contract(
    contract: Path = ContractArgument,
    pair: list[str] = PairOption,
    workspace_root: Path | None = WorkspaceRootOption,
) -> None:
    workspace = _resolve_workspace(workspace_root)

    contract_path = _resolve_contract_path(contract, workspace)
    candidate_contract = load_candidate_contract(contract_path)

    training_pairs = {
        (item.source_execution, item.target_execution)
        for item in candidate_contract.paired_executions
    }

    validation_pairs = []

    for raw_pair in pair:
        source_id, target_id = _parse_pair(raw_pair)

        if (source_id, target_id) in training_pairs:
            raise typer.BadParameter(
                f"{source_id}:{target_id} was used to infer this contract. "
                "Use held-out executions for validation."
            )

        source_path = workspace.executions / f"{source_id}.json"
        target_path = workspace.executions / f"{target_id}.json"

        if not source_path.exists():
            raise typer.BadParameter(f"Source execution not found: {source_id}")
        if not target_path.exists():
            raise typer.BadParameter(f"Target execution not found: {target_id}")

        validation_pairs.append(
            (
                ExecutionPairRef(
                    source_execution=source_id,
                    target_execution=target_id,
                ),
                load_execution_observations(source_path),
                load_execution_observations(target_path),
            )
        )

    result = validate_candidate_contract(candidate_contract, validation_pairs)

    output_path = save_contract_validation(
        result,
        contract=candidate_contract,
        directory=workspace.results,
        contract_path=contract_path,
    )

    typer.echo(f"Contract validation: {result.verdict.value}")

    for pair_result in result.pairs:
        typer.echo("")
        typer.echo(
            f"{pair_result.pair.source_execution}"
            " <-> "
            f"{pair_result.pair.target_execution}"
            f": {pair_result.verdict.value}"
        )
        for item in pair_result.correspondences:
            typer.echo(f"  {item.source.locator} <-> {item.target.locator}: {item.verdict.value}")
        for expression_item in pair_result.expression_correspondences:
            typer.echo(
                f"  {_expression_label(expression_item.source)} <-> "
                f"{_expression_label(expression_item.target)}: "
                f"{expression_item.verdict.value}"
            )

    typer.echo("")
    typer.echo(f"Saved: {output_path}")


def _resolve_contract_path(
    contract: Path,
    workspace: WorkspacePaths,
) -> Path:
    path = contract.expanduser()

    if path.is_absolute() or path.exists():
        resolved = path.resolve()
    else:
        resolved = (workspace.contracts / path).resolve()

    if not resolved.is_file():
        raise typer.BadParameter(f"Contract not found: {contract}")

    return resolved


def _expression_label(expression: EntityExpression) -> str:
    components = " + ".join(component.locator for component in expression.components)
    if len(expression.components) == 1:
        return components
    return f"{expression.kind.value}({components})"
