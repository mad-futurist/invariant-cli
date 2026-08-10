import typer

from invariant_cli.commands.capture import capture_command
from invariant_cli.commands.compare import compare_command
from invariant_cli.commands.contract import contract_app
from invariant_cli.commands.init import init_command

app = typer.Typer(
    name="invariant",
    help="Deterministic verification infrastructure for software evolution.",
    no_args_is_help=True,
)


@app.callback()
def main_callback() -> None:
    """Manage Invariant CLI commands."""


@app.command(name="version")
def version() -> None:
    """Print the version of Invariant."""
    typer.echo("Invariant CLI 0.1.0")


app.command(name="init")(init_command)
app.command(name="capture")(capture_command)
app.command(name="compare")(compare_command)

app.add_typer(
    contract_app,
    name="contract",
)


def main() -> None:
    app()
