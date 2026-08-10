from invariant_cli.contracts.model import CorrespondenceCandidate
from invariant_cli.contracts.relations import infer_relation
from invariant_cli.matching.model import (
    EntityKind,
    EntityRef,
    Evidence,
    EvidenceKind,
)
from invariant_cli.matching.transition import (
    ObservationKey,
    ObservedTransition,
    flatten_observations,
    transition_fingerprint,
)
from invariant_cli.observation.model import Observation

MISSING = object()


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
            {transition_fingerprint(transition) for transition in typed_source_transitions}
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

            relation = infer_relation(
                typed_source_transitions,
                typed_target_transitions,
            )

            if relation is None:
                continue

            source_observation_kind, source_resource, source_path = source_key
            target_observation_kind, target_resource, target_path = target_key
            source_entity_kind = _entity_kind(source_observation_kind)
            target_entity_kind = _entity_kind(target_observation_kind)

            if source_entity_kind is None or target_entity_kind is None:
                continue

            candidates.append(
                CorrespondenceCandidate(
                    source=EntityRef(
                        kind=source_entity_kind,
                        namespace=source_resource,
                        identifier=source_path,
                    ),
                    target=EntityRef(
                        kind=target_entity_kind,
                        namespace=target_resource,
                        identifier=target_path,
                    ),
                    relation=relation,
                    evidence=[
                        Evidence(
                            kind=EvidenceKind.DYNAMIC_TRANSITION,
                            producer="dynamic-transition-v1",
                            attributes={
                                "matched_pairs": len(pairs),
                                "total_pairs": len(pairs),
                                "distinct_transitions": distinct_transitions,
                            },
                        )
                    ],
                )
            )

    return candidates


def _entity_kind(observation_kind: str) -> EntityKind | None:
    if observation_kind == "json":
        return EntityKind.JSON_FIELD
    if observation_kind == "sqlite":
        return EntityKind.SQLITE_FIELD
    return None


def transitions_equal(
    source: ObservedTransition,
    target: ObservedTransition,
) -> bool:
    from invariant_cli.matching.transition import transitions_equal as _eq

    return _eq(source, target)
