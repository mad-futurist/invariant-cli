from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Invariant CLI 0.1.0" in result.output
