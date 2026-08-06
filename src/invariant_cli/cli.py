import typer

app = typer.Typer(
    name="invariant",
    help="Deterministic verification infrasstructure for software evolutions.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Print the version of invariant."""
    typer.echo("Invariant CLI 0.1.0")
