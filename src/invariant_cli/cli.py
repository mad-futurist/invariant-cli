import typer

app = typer.Typer(
    name="invariant",
    help="Deterministic verification infrasstructure for software evolutions.",
    no_args_is_help=True,
)


@app.callback()
def main_callback() -> None:
    """Manage invariant CLI commands."""


@app.command(name="version")
def version() -> None:
    """Print the version of invariant."""
    typer.echo("Invariant CLI 0.1.0")


def main() -> None:
    app()
