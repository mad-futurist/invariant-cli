from invariant_cli.contracts.generation import InferenceLimits, shortlist_direct_targets
from invariant_cli.contracts.model import CorrespondenceCandidate
from invariant_cli.contracts.relations import infer_relation
from invariant_cli.matching.model import (
    Evidence,
    EvidenceKind,
)
from invariant_cli.matching.schema.model import SchemaProfile
from invariant_cli.matching.schema.observed import build_schema_evidence, profile_observed_field
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
    *,
    limits: InferenceLimits | None = None,
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

    limits = limits or InferenceLimits()
    source_profiles = _profiles(source_keys, [source for source, _ in flattened_pairs])
    target_profiles = _profiles(target_keys, [target for _, target in flattened_pairs])
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

        source_profile = source_profiles.get(source_key)
        if source_profile is None:
            continue

        for target_key in shortlist_direct_targets(
            source_profile,
            target_profiles,
            limit=limits.max_direct_targets_per_source,
        ):
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

            target_profile = target_profiles.get(target_key)
            if target_profile is None:
                continue

            candidates.append(
                CorrespondenceCandidate(
                    source=source_profile.entity,
                    target=target_profile.entity,
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
                        ),
                        build_schema_evidence(source_profile, (target_profile,)),
                    ],
                )
            )

    return candidates


def _profiles(
    keys: set[ObservationKey],
    observations: list[dict[ObservationKey, ObservedTransition]],
) -> dict[ObservationKey, SchemaProfile]:
    profiles: dict[ObservationKey, SchemaProfile] = {}
    for key in keys:
        profile = profile_observed_field(
            key,
            (values[key] for values in observations if key in values),
        )
        if profile is not None:
            profiles[key] = profile
    return profiles


def transitions_equal(
    source: ObservedTransition,
    target: ObservedTransition,
) -> bool:
    from invariant_cli.matching.transition import transitions_equal as _eq

    return _eq(source, target)
