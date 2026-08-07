import os
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()


def test_init_creates_workspace() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        original_cwd = Path.cwd()
        try:
            os.chdir(Path(tmp_dir).resolve())
            result = runner.invoke(
                app,
                ["init", "--name", "test-project"],
            )

            assert result.exit_code == 0

            root = Path(".invariant")

            assert root.exists()
            assert (root / "invariant.yaml").exists()
            assert (root / "cases").exists()
            assert (root / "observations").exists()
            assert (root / "contracts").exists()
            assert (root / "gates").exists()
            assert (root / "results").exists()
        finally:
            os.chdir(original_cwd)


def test_init_fails_if_workspace_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        original_cwd = Path.cwd()
        try:
            os.chdir(Path(tmp_dir).resolve())
            first = runner.invoke(app, ["init"])
            second = runner.invoke(app, ["init"])

            assert first.exit_code == 0
            assert second.exit_code == 1
            assert "already exists" in second.stderr
        finally:
            os.chdir(original_cwd)
