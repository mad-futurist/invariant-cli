import json
from pathlib import Path

from invariant_cli.observation.model import Observation, ValueChange


def load_execution_observations(
    path: Path,
) -> list[Observation]:
    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))

    return [
        Observation(
            source=entry["source"],
            kind=entry["kind"],
            changes=[
                ValueChange(
                    path=change["path"],
                    before=change["before"],
                    after=change["after"],
                )
                for change in entry.get("changes", [])
            ],
        )
        for entry in data.get("observations", [])
    ]
