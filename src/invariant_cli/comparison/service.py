from invariant_cli.comparison.model import (
    ComparisonResult,
    ObservationDifference,
)
from invariant_cli.observation.model import Observation


def compare_observations(
    source: list[Observation],
    target: list[Observation],
) -> ComparisonResult:
    source_values = _index_observations(source)
    target_values = _index_observations(target)

    differences: list[ObservationDifference] = []

    keys = source_values.keys() | target_values.keys()

    for key in sorted(keys):
        source_name, path = key

        expected = source_values.get(key)
        actual = target_values.get(key)

        if expected != actual:
            differences.append(
                ObservationDifference(
                    source=source_name,
                    path=path,
                    expected=expected,
                    actual=actual,
                )
            )

    return ComparisonResult(
        matches=not differences,
        differences=differences,
    )


def _index_observations(
    observations: list[Observation],
) -> dict[tuple[str, str], object]:
    values: dict[tuple[str, str], object] = {}

    for observation in observations:
        for change in observation.changes:
            values[(observation.source, change.path)] = change.after

    return values
