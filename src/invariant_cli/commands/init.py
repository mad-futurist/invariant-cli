from pathlib import Path

import typer

from invariant_cli.workspace.service import WorkspaceAlreadyExistsError, initialize_workspace


def init_command(
    name: str = typer.Option(
        "invariant-project",
        "--name",
        help="Project name.",
    ),
) -> None:
    """Initialize an Invariant workspace."""

    root = Path.cwd()

    try:
        paths = initialize_workspace(
            root,
            name=name,
        )
    except WorkspaceAlreadyExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Initialized Invariant workspace.")
    typer.echo(f"Location: {paths.invariant_dir}")
