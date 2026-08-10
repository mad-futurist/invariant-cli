import json
import os
from pathlib import Path

import yaml
from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()


def write_execution(
    directory: Path,
    execution_id: str,
    *,
    resource: str,
    path: str,
    before: object,
    after: object,
) -> None:
    data = {
        "id": execution_id,
        "command": ["python", "app.py"],
        "working_directory": str(directory),
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:01+00:00",
        "duration_seconds": 1.0,
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "filesystem_diff": {
            "created": [],
            "deleted": [],
            "modified": [],
        },
        "observations": [
            {
                "source": resource,
                "kind": "json",
                "changes": [
                    {
                        "path": path,
                        "before": before,
                        "after": after,
                    }
                ],
            }
        ],
    }

    (directory / f"{execution_id}.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def test_contract_infer_command(tmp_path: Path) -> None:
    original_cwd = Path.cwd()

    try:
        os.chdir(tmp_path)

        init_result = runner.invoke(app, ["init", "--name", "demo"])

        assert init_result.exit_code == 0

        executions = tmp_path / ".invariant" / "executions"

        runs = [
            ("source-1", "target-1", 100, 70),
            ("source-2", "target-2", 100, 40),
            ("source-3", "target-3", 250, 190),
        ]

        for source_id, target_id, before, after in runs:
            write_execution(
                executions,
                source_id,
                resource="state.json",
                path="balance",
                before=before,
                after=after,
            )

            write_execution(
                executions,
                target_id,
                resource="account.json",
                path="remaining",
                before=before,
                after=after,
            )

        result = runner.invoke(
            app,
            [
                "contract",
                "infer",
                "--pair",
                "source-1:target-1",
                "--pair",
                "source-2:target-2",
                "--pair",
                "source-3:target-3",
            ],
        )

        assert result.exit_code == 0

        assert "Candidate correspondences: 1" in result.stdout

        contracts = tmp_path / ".invariant" / "contracts"

        files = list(contracts.glob("*.candidate.yaml"))

        assert len(files) == 1

        data = yaml.safe_load(files[0].read_text(encoding="utf-8"))

        assert data["version"] == 1
        assert data["status"] == "candidate"

        assert len(data["paired_executions"]) == 3

        correspondences = data["correspondences"]

        assert len(correspondences) == 1

        correspondence = correspondences[0]

        assert correspondence["source"] == {
            "resource": "state.json",
            "path": "balance",
        }

        assert correspondence["target"] == {
            "resource": "account.json",
            "path": "remaining",
        }

        dynamic = correspondence["evidence"]["dynamic"]

        assert dynamic["matched_pairs"] == 3
        assert dynamic["total_pairs"] == 3
        assert dynamic["distinct_transitions"] == 3
        assert dynamic["score"] == 1.0

    finally:
        os.chdir(original_cwd)
