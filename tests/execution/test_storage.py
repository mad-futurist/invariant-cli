import json
import sys
from pathlib import Path

from invariant_cli.execution.service import capture_process
from invariant_cli.execution.storage import save_execution


def test_save_execution(tmp_path: Path) -> None:
    execution = capture_process(
        [
            sys.executable,
            "-c",
            "print('captured')",
        ],
        working_directory=tmp_path,
    )

    executions_dir = tmp_path / "executions"

    output_path = save_execution(
        execution,
        directory=executions_dir,
    )

    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["id"] == execution.id
    assert data["exit_code"] == 0
    assert data["stdout"].strip() == "captured"
