from typer.testing import CliRunner

from invariant_cli import main as package_main
from invariant_cli.cli import app
from invariant_cli.observation import observe_json

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Invariant CLI 0.1.0" in result.output


def test_package_main_is_callable() -> None:
    assert callable(package_main)


def test_json_observation_detects_nested_change() -> None:
    before = """
    {
        "account": {
            "balance": 100,
            "status": "active"
        }
    }
    """

    after = """
    {
        "account": {
            "balance": 70,
            "status": "active"
        }
    }
    """

    observation = observe_json("state.json", before, after)

    assert len(observation.changes) == 1

    change = observation.changes[0]

    assert change.path == "account.balance"
    assert change.before == 100
    assert change.after == 70
