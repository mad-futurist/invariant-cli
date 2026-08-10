from pathlib import Path

import typer

from invariant_cli.contracts.inference import infer_correspondences
from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    ExecutionPairRef,
)
from invariant_cli.contracts.storage import save_candidate_contract
from invariant_cli.execution.reader import load_execution_observations
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


@contract_app.command("infer")
def infer_contract(
    pair: list[str] = PairOption,
    workspace_root: Path | None = WorkspaceRootOption,
) -> None:
    workspace = _resolve_workspace(
        workspace_root,
    )

    if len(pair) < 3:
        raise typer.BadParameter("Contract inference requires at least 3 paired executions.")

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

    contract = CandidateTranslationContract(
        version=1,
        paired_executions=pair_refs,
        correspondences=candidates,
    )

    output_path = save_candidate_contract(
        contract,
        directory=workspace.contracts,
    )

    typer.echo(f"Paired executions: {len(pair_refs)}")

    typer.echo(f"Candidate correspondences: {len(candidates)}")

    if candidates:
        typer.echo("")

        for candidate in candidates:
            typer.echo(f"{candidate.source.resource}#{candidate.source.path}")

            typer.echo("  <->")

            typer.echo(f"{candidate.target.resource}#{candidate.target.path}")

            typer.echo(
                "  dynamic evidence: "
                f"{candidate.evidence.matched_pairs}/"
                f"{candidate.evidence.total_pairs}"
            )

            typer.echo(f"  distinct transitions: {candidate.evidence.distinct_transitions}")

            typer.echo("")
    else:
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
