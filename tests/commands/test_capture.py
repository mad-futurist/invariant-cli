import json
import os
import sys
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()


def test_capture_records_filesystem_created_file() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        original_cwd = Path.cwd()
        try:
            os.chdir(Path(tmp_dir).resolve())

            init_result = runner.invoke(app, ["init", "--name", "demo"])
            assert init_result.exit_code == 0

            capture_result = runner.invoke(
                app,
                [
                    "capture",
                    "--",
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('created-by-capture.txt').write_text('x')",
                ],
            )

            assert capture_result.exit_code == 0

            executions_dir = Path(".invariant") / "executions"
            execution_files = sorted(executions_dir.glob("*.json"))
            assert len(execution_files) == 1

            data = json.loads(execution_files[0].read_text(encoding="utf-8"))

            assert data["filesystem_diff"]["created"] == ["created-by-capture.txt"]
            assert data["filesystem_diff"]["deleted"] == []
            assert data["filesystem_diff"]["modified"] == []
        finally:
            os.chdir(original_cwd)


def test_capture_records_json_observation_for_modified_json_file(tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        init_result = runner.invoke(app, ["init", "--name", "demo"])
        assert init_result.exit_code == 0

        state_path = tmp_path / "state.json"
        state_path.write_text('{"price": 1}\n', encoding="utf-8")

        capture_result = runner.invoke(
            app,
            [
                "capture",
                "--",
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "Path('state.json').write_text('{\"price\": 2}\\n', encoding='utf-8')"
                ),
            ],
        )

        assert capture_result.exit_code == 0

        executions_dir = tmp_path / ".invariant" / "executions"
        execution_files = sorted(executions_dir.glob("*.json"))
        assert len(execution_files) == 1

        data = json.loads(execution_files[0].read_text(encoding="utf-8"))
        assert data["observations"][0]["kind"] == "json"
        assert data["observations"][0]["changes"][0]["path"] == "price"
        assert data["observations"][0]["changes"][0]["before"] == 1
        assert data["observations"][0]["changes"][0]["after"] == 2
    finally:
        os.chdir(original_cwd)


def test_capture_uses_explicit_workspace_root_from_another_directory(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    original_cwd = Path.cwd()
    try:
        os.chdir(workspace_root)
        init_result = runner.invoke(app, ["init", "--name", "demo"])
        assert init_result.exit_code == 0

        os.chdir(outside_dir)

        capture_result = runner.invoke(
            app,
            [
                "capture",
                "--workspace-root",
                str(workspace_root),
                "--",
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "Path('created-by-capture-explicit-root.txt').write_text('x')"
                ),
            ],
        )

        assert capture_result.exit_code == 0

        created_file = workspace_root / "created-by-capture-explicit-root.txt"
        assert created_file.exists()

        executions_dir = workspace_root / ".invariant" / "executions"
        execution_files = sorted(executions_dir.glob("*.json"))
        assert len(execution_files) == 1

        data = json.loads(execution_files[0].read_text(encoding="utf-8"))

        assert data["working_directory"] == str(workspace_root)
        assert data["filesystem_diff"]["created"] == ["created-by-capture-explicit-root.txt"]
        assert data["filesystem_diff"]["deleted"] == []
        assert data["filesystem_diff"]["modified"] == []
    finally:
        os.chdir(original_cwd)


def test_capture_limits_filesystem_diff_to_observe_scope(tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert runner.invoke(app, ["init", "--name", "demo"]).exit_code == 0

        (tmp_path / "state.json").write_text('{"value": 1}', encoding="utf-8")
        (tmp_path / "unrelated.txt").write_text("before", encoding="utf-8")

        command = (
            "from pathlib import Path; "
            "Path('state.json').write_text('{\"value\": 2}', encoding='utf-8'); "
            "Path('unrelated.txt').write_text('after', encoding='utf-8')"
        )
        result = runner.invoke(
            app,
            [
                "capture",
                "--observe",
                "*.json",
                "--",
                sys.executable,
                "-c",
                command,
            ],
        )

        assert result.exit_code == 0, result.stdout
        execution_file = next((tmp_path / ".invariant" / "executions").glob("*.json"))
        data = json.loads(execution_file.read_text(encoding="utf-8"))
        assert data["filesystem_diff"]["modified"] == ["state.json"]
        assert data["observations"][0]["source"] == "state.json"
    finally:
        os.chdir(original_cwd)
