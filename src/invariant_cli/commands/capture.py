from pathlib import Path

import typer

from invariant_cli.execution.service import capture_process
from invariant_cli.execution.storage import save_execution
from invariant_cli.workspace.service import load_workspace_paths

CommandArgument = typer.Argument(..., help="Command to execute and capture.")


def capture_command(command: list[str] = CommandArgument) -> None:
    launch_dir = Path.cwd()
    try:
        workspace = load_workspace_paths(launch_dir)
    except FileNotFoundError as exc:
        raise typer.BadParameter(
            "No Invariant workspace found from "
            f"{launch_dir}. Run 'invariant init' in the project root first."
        ) from exc

    execution = capture_process(
        command,
        working_directory=workspace.root,
    )

    output_path = save_execution(
        execution,
        directory=workspace.executions,
    )

    typer.echo(f"Execution: {execution.id}")
    typer.echo(f"Exit code: {execution.exit_code}")
    typer.echo(f"Duration: {execution.duration_seconds:.3f}s")
    typer.echo(f"Saved: {output_path}")
