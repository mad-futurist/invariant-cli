from typer.testing import CliRunner

from invariant_cli import main as package_main
from invariant_cli.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Invariant CLI 0.1.0" in result.output


def test_package_main_is_callable() -> None:
    assert callable(package_main)
