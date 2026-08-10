import json
from dataclasses import dataclass
from typing import Any

from invariant_cli.observation.model import Observation, serialize_value

ObservationKey = tuple[str, str, str]


@dataclass(frozen=True)
class ObservedTransition:
    before: Any
    after: Any


def flatten_observations(
    observations: list[Observation],
) -> dict[ObservationKey, ObservedTransition]:
    transitions: dict[ObservationKey, ObservedTransition] = {}

    for observation in observations:
        for change in observation.changes:
            transitions[(observation.kind, observation.source, change.path)] = ObservedTransition(
                before=change.before,
                after=change.after,
            )

    return transitions


def values_equal(source: Any, target: Any) -> bool:
    # bool is a subclass of int in Python; True must not silently match 1.
    if isinstance(source, bool) or isinstance(target, bool):
        return type(source) is type(target) and source == target

    if isinstance(source, (int, float)) and isinstance(target, (int, float)):
        return source == target

    return type(source) is type(target) and source == target


def transitions_equal(
    source: ObservedTransition,
    target: ObservedTransition,
) -> bool:
    return values_equal(source.before, target.before) and values_equal(source.after, target.after)


def transition_fingerprint(transition: ObservedTransition) -> str:
    return json.dumps(
        {
            "before": serialize_value(transition.before),
            "after": serialize_value(transition.after),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
