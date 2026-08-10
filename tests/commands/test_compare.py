import json
import os
from pathlib import Path

from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()


def test_compare_command_persists_results(tmp_path: Path) -> None:
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)

        init_result = runner.invoke(app, ["init", "--name", "demo"])
        assert init_result.exit_code == 0

        executions_dir = tmp_path / ".invariant" / "executions"
        executions_dir.mkdir(parents=True, exist_ok=True)

        source_path = executions_dir / "source.json"
        target_path = executions_dir / "target.json"

        source_path.write_text(
            json.dumps(
                {
                    "id": "source",
                    "command": ["python", "app.py"],
                    "working_directory": str(tmp_path),
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:00:01+00:00",
                    "duration_seconds": 1.0,
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "filesystem_diff": {"created": [], "deleted": [], "modified": []},
                    "observations": [
                        {
                            "source": "state.json",
                            "kind": "json",
                            "changes": [
                                {
                                    "path": "payment.status",
                                    "before": "PENDING",
                                    "after": "COMPLETED",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        target_path.write_text(
            json.dumps(
                {
                    "id": "target",
                    "command": ["python", "app.py"],
                    "working_directory": str(tmp_path),
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:00:01+00:00",
                    "duration_seconds": 1.0,
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "filesystem_diff": {"created": [], "deleted": [], "modified": []},
                    "observations": [],
                }
            ),
            encoding="utf-8",
        )

        result = runner.invoke(app, ["compare", "source", "target"])

        assert result.exit_code == 0
        result_files = sorted((tmp_path / ".invariant" / "results").glob("*.json"))
        assert len(result_files) == 1

        data = json.loads(result_files[0].read_text(encoding="utf-8"))
        assert data["matches"] is False
        assert data["differences"][0]["expected"] == "COMPLETED"
        assert data["differences"][0]["actual"] == "<missing>"
    finally:
        os.chdir(original_cwd)
