from pathlib import Path

import typer

from invariant_cli.execution.service import capture_execution
from invariant_cli.execution.storage import save_execution
from invariant_cli.workspace.service import get_workspace_paths, load_workspace_paths

CommandArgument = typer.Argument(..., help="Command to execute and capture.")
WorkspaceRootOption = typer.Option(
    None,
    "--workspace-root",
    "-w",
    help=(
        "Path to the project root that contains .invariant. "
        "When provided, filesystem snapshots and command execution run from this root."
    ),
)
ObserveOption = typer.Option(
    None,
    "--observe",
    help=(
        "Workspace-relative file or glob to capture. "
        "Pass multiple times to combine scopes. Defaults to the whole workspace."
    ),
)


def capture_command(
    command: list[str] = CommandArgument,
    workspace_root: Path | None = WorkspaceRootOption,
    observe: list[str] | None = ObserveOption,
) -> None:
    launch_dir = Path.cwd()

    if workspace_root is not None:
        analysis_root = workspace_root.expanduser().resolve()
        invariant_dir = analysis_root / ".invariant"
        if not invariant_dir.is_dir():
            raise typer.BadParameter(
                f"{analysis_root} does not contain a .invariant directory. "
                "Pass the project root path (the folder that directly contains .invariant)."
            )
        workspace = get_workspace_paths(analysis_root)
    else:
        analysis_root = launch_dir
        try:
            workspace = load_workspace_paths(launch_dir)
        except FileNotFoundError as exc:
            raise typer.BadParameter(
                "No Invariant workspace found from "
                f"{launch_dir}. Run 'invariant init' in the project root first "
                "or pass --workspace-root."
            ) from exc

    if len(command) == 1 and Path(command[0]).is_dir():
        raise typer.BadParameter(
            f"'{command[0]}' is a directory, not an executable command. "
            "Provide the command to run, e.g.: invariant capture python app.py"
        )

    try:
        execution, observations = capture_execution(
            command,
            working_directory=analysis_root,
            include_patterns=observe,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    output_path = save_execution(
        execution,
        directory=workspace.executions,
        observations=observations,
    )

    typer.echo(f"Execution: {execution.id}")
    typer.echo(f"Exit code: {execution.exit_code}")
    typer.echo(f"Duration: {execution.duration_seconds:.3f}s")
    typer.echo(f"Saved: {output_path}")
