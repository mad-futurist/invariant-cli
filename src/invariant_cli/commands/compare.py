import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from invariant_cli.comparison.service import compare_observations
from invariant_cli.observation.model import Observation, ValueChange
from invariant_cli.workspace.service import get_workspace_paths, load_workspace_paths


def compare_command(
    source_execution: str,
    target_execution: str,
    workspace_root: Path | None = None,
) -> None:
    launch_dir = Path.cwd()

    if workspace_root is not None:
        analysis_root = workspace_root.expanduser().resolve()
        workspace = get_workspace_paths(analysis_root)
    else:
        workspace = load_workspace_paths(launch_dir)

    source_path = workspace.executions / f"{source_execution}.json"
    target_path = workspace.executions / f"{target_execution}.json"

    if not source_path.exists():
        raise typer.BadParameter(f"Source execution not found: {source_execution}")
    if not target_path.exists():
        raise typer.BadParameter(f"Target execution not found: {target_execution}")

    source_execution_data = json.loads(source_path.read_text(encoding="utf-8"))
    target_execution_data = json.loads(target_path.read_text(encoding="utf-8"))

    source_observations = [
        Observation(
            source=entry["source"],
            kind=entry["kind"],
            changes=[
                ValueChange(
                    path=change["path"],
                    before=change["before"],
                    after=change["after"],
                )
                for change in entry["changes"]
            ],
        )
        for entry in source_execution_data.get("observations", [])
    ]

    target_observations = [
        Observation(
            source=entry["source"],
            kind=entry["kind"],
            changes=[
                ValueChange(
                    path=change["path"],
                    before=change["before"],
                    after=change["after"],
                )
                for change in entry["changes"]
            ],
        )
        for entry in target_execution_data.get("observations", [])
    ]

    result = compare_observations(source_observations, target_observations)

    workspace.results.mkdir(parents=True, exist_ok=True)
    result_path = workspace.results / f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
    result_path.write_text(
        json.dumps(
            {
                "source_execution": source_execution,
                "target_execution": target_execution,
                "matches": result.matches,
                "differences": [
                    {
                        "source": difference.source,
                        "path": difference.path,
                        "expected": difference.expected,
                        "actual": difference.actual,
                    }
                    for difference in result.differences
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if result.matches:
        typer.echo("Comparison: MATCH")
        typer.echo("No observable differences found.")
    else:
        typer.echo("Comparison: FAILED")
        for difference in result.differences:
            typer.echo(f"{difference.source}")
            typer.echo(f"  {difference.path}")
            typer.echo(f"    source: {difference.expected}")
            typer.echo(f"    target: {difference.actual}")
        typer.echo(f"{len(result.differences)} difference found.")

    typer.echo(f"Saved: {result_path}")
