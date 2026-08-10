from typing import Any

from invariant_cli.observation.model import ABSENT, ValueChange


def diff_json(
    before: Any,
    after: Any,
    path: str = "",
) -> list[ValueChange]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[ValueChange] = []

        keys = before.keys() | after.keys()

        for key in sorted(keys):
            child_path = f"{path}.{key}" if path else key

            if key not in before:
                changes.append(
                    ValueChange(
                        path=child_path,
                        before=ABSENT,
                        after=after[key],
                    )
                )
                continue

            if key not in after:
                changes.append(
                    ValueChange(
                        path=child_path,
                        before=before[key],
                        after=ABSENT,
                    )
                )
                continue

            changes.extend(
                diff_json(
                    before[key],
                    after[key],
                    child_path,
                )
            )

        return changes

    if before != after:
        return [
            ValueChange(
                path=path,
                before=before,
                after=after,
            )
        ]

    return []
