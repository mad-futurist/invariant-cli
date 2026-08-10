import json
from dataclasses import dataclass
from typing import Any

from invariant_cli.contracts.model import (
    CorrespondenceCandidate,
    DynamicEvidence,
    ObservationSelector,
)
from invariant_cli.observation.model import Observation, _AbsentType

ObservationKey = tuple[str, str]

MISSING = object()


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
            key = (
                observation.source,
                change.path,
            )

            transitions[key] = ObservedTransition(
                before=change.before,
                after=change.after,
            )

    return transitions


def infer_correspondences(
    pairs: list[
        tuple[
            list[Observation],
            list[Observation],
        ]
    ],
) -> list[CorrespondenceCandidate]:
    if not pairs:
        return []

    flattened_pairs = [
        (
            flatten_observations(source),
            flatten_observations(target),
        )
        for source, target in pairs
    ]

    source_keys: set[ObservationKey] = set()
    target_keys: set[ObservationKey] = set()

    for source_values, target_values in flattened_pairs:
        source_keys.update(source_values)
        target_keys.update(target_values)

    candidates: list[CorrespondenceCandidate] = []

    for source_key in sorted(source_keys):
        source_transitions = [
            source_values.get(source_key, MISSING) for source_values, _ in flattened_pairs
        ]

        # For the first version we only infer relations that
        # were observed in every paired execution.
        if any(value is MISSING for value in source_transitions):
            continue

        typed_source_transitions = [
            value for value in source_transitions if isinstance(value, ObservedTransition)
        ]

        distinct_transitions = len(
            {_transition_fingerprint(transition) for transition in typed_source_transitions}
        )

        # Repeating exactly the same transition does not provide
        # enough dynamic evidence.
        if distinct_transitions < 2:
            continue

        for target_key in sorted(target_keys):
            target_transitions = [
                target_values.get(target_key, MISSING) for _, target_values in flattened_pairs
            ]

            if any(value is MISSING for value in target_transitions):
                continue

            typed_target_transitions = [
                value for value in target_transitions if isinstance(value, ObservedTransition)
            ]

            matched_pairs = sum(
                transitions_equal(source_transition, target_transition)
                for source_transition, target_transition in zip(
                    typed_source_transitions,
                    typed_target_transitions,
                    strict=True,
                )
            )

            if matched_pairs != len(pairs):
                continue

            source_resource, source_path = source_key
            target_resource, target_path = target_key

            candidates.append(
                CorrespondenceCandidate(
                    source=ObservationSelector(
                        resource=source_resource,
                        path=source_path,
                    ),
                    target=ObservationSelector(
                        resource=target_resource,
                        path=target_path,
                    ),
                    evidence=DynamicEvidence(
                        matched_pairs=matched_pairs,
                        total_pairs=len(pairs),
                        distinct_transitions=distinct_transitions,
                    ),
                )
            )

    return candidates


def transitions_equal(
    source: ObservedTransition,
    target: ObservedTransition,
) -> bool:
    return values_equal(
        source.before,
        target.before,
    ) and values_equal(
        source.after,
        target.after,
    )


def values_equal(
    source: Any,
    target: Any,
) -> bool:
    # python considers True == 1 which is undesirable here
    if isinstance(source, bool) or isinstance(target, bool):
        return type(source) is type(target) and source == target

    # json 70 and 70.0 can be treated as the
    # same numeric value at this stage
    if isinstance(source, (int, float)) and isinstance(target, (int, float)):
        return source == target

    return type(source) is type(target) and source == target


def _transition_fingerprint(
    transition: ObservedTransition,
) -> str:
    def _default(obj: Any) -> Any:
        if isinstance(obj, _AbsentType):
            return "__absent__"
        raise TypeError(f"Not serializable: {type(obj)}")

    return json.dumps(
        {
            "before": transition.before,
            "after": transition.after,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_default,
    )
