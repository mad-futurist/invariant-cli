import json
from pathlib import Path

from invariant_cli.execution.model import Execution


def save_execution(
    execution: Execution,
    *,
    directory: Path,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{execution.id}.json"

    data = {
        "id": execution.id,
        "command": execution.command,
        "working_directory": str(execution.working_directory),
        "started_at": execution.started_at.isoformat(),
        "finished_at": execution.finished_at.isoformat(),
        "duration_seconds": execution.duration_seconds,
        "exit_code": execution.exit_code,
        "stdout": execution.stdout,
        "stderr": execution.stderr,
    }

    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    return output_path
