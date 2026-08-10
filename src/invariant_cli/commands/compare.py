import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from invariant_cli.comparison.model import ComparisonVerdict
from invariant_cli.comparison.service import MISSING, compare_observations
from invariant_cli.execution.reader import load_execution_observations
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

    source_observations = load_execution_observations(source_path)
    target_observations = load_execution_observations(target_path)

    result = compare_observations(source_observations, target_observations)

    def _format_value(value: object) -> str:
        if value is MISSING:
            return "<missing>"
        return str(value)

    workspace.results.mkdir(parents=True, exist_ok=True)
    result_path = workspace.results / f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
    result_path.write_text(
        json.dumps(
            {
                "source_execution": source_execution,
                "target_execution": target_execution,
                "verdict": result.verdict.value,
                "matches": result.matches,
                "differences": [
                    {
                        "source": difference.source,
                        "path": difference.path,
                        "expected": _format_value(difference.expected),
                        "actual": _format_value(difference.actual),
                    }
                    for difference in result.differences
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    typer.echo(f"Comparison: {result.verdict.value}")
    if result.verdict == ComparisonVerdict.INCONCLUSIVE:
        typer.echo("No comparable observations found.")
    elif result.verdict == ComparisonVerdict.MATCH:
        typer.echo("No observable differences found.")
    else:
        for difference in result.differences:
            typer.echo(f"{difference.source}")
            typer.echo(f"  {difference.path}")
            typer.echo(f"    source: {_format_value(difference.expected)}")
            typer.echo(f"    target: {_format_value(difference.actual)}")
        typer.echo(f"{len(result.differences)} difference(s) found.")

    typer.echo(f"Saved: {result_path}")
