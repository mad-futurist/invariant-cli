import json
from pathlib import Path

from invariant_cli.execution.model import Execution
from invariant_cli.observation.model import Observation


def save_execution(
    execution: Execution,
    *,
    directory: Path,
    observations: list[Observation] | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{execution.id}.json"

    serialized_observations = [
        {
            "source": observation.source,
            "kind": observation.kind,
            "changes": [
                {
                    "path": change.path,
                    "before": change.before,
                    "after": change.after,
                }
                for change in observation.changes
            ],
        }
        for observation in (observations or [])
    ]

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
        "filesystem_diff": {
            "created": [str(path) for path in execution.filesystem_diff.created],
            "deleted": [str(path) for path in execution.filesystem_diff.deleted],
            "modified": [str(path) for path in execution.filesystem_diff.modified],
        },
        "observations": serialized_observations,
    }

    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    return output_path
