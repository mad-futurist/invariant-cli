from invariant_cli.contracts.generation import InferenceLimits, shortlist_expression_targets
from invariant_cli.contracts.model import (
    EntityExpression,
    ExpressionCorrespondenceCandidate,
    ExpressionKind,
)
from invariant_cli.contracts.relations import infer_relation, to_decimal
from invariant_cli.matching.model import Evidence, EvidenceFamily, EvidenceKind
from invariant_cli.matching.schema.model import SchemaProfile
from invariant_cli.matching.schema.observed import build_schema_evidence, profile_observed_field
from invariant_cli.matching.transition import (
    ObservationKey,
    ObservedTransition,
    flatten_observations,
    transition_fingerprint,
)
from invariant_cli.observation.model import Observation

SUM_COMPONENT_COUNT = 2
PRODUCER = "dynamic-sum-v1"


def infer_expression_correspondences(
    pairs: list[tuple[list[Observation], list[Observation]]],
    *,
    limits: InferenceLimits | None = None,
) -> list[ExpressionCorrespondenceCandidate]:
    """Infer one source entity against the sum of exactly two target entities."""
    if not pairs:
        return []

    flattened_pairs = [
        (flatten_observations(source), flatten_observations(target)) for source, target in pairs
    ]
    source_keys = sorted({key for source, _ in flattened_pairs for key in source})
    target_keys = sorted({key for _, target in flattened_pairs for key in target})
    limits = limits or InferenceLimits()
    source_profiles = _profiles(source_keys, [source for source, _ in flattened_pairs])
    target_profiles = _profiles(target_keys, [target for _, target in flattened_pairs])
    candidates: list[ExpressionCorrespondenceCandidate] = []

    for source_key in source_keys:
        source_transitions = _transitions_for(source_key, [source for source, _ in flattened_pairs])
        if source_transitions is None or _distinct_count(source_transitions) < 2:
            continue

        source_profile = source_profiles.get(source_key)
        if source_profile is None:
            continue

        for target_key_pair in shortlist_expression_targets(
            source_profile,
            target_profiles,
            component_count=SUM_COMPONENT_COUNT,
            limit=limits.max_expression_pairs_per_source,
        ):
            target_transitions = _summed_transitions(
                target_key_pair,
                [target for _, target in flattened_pairs],
            )
            if target_transitions is None:
                continue

            typed_target_profiles = tuple(target_profiles[key] for key in target_key_pair)
            if len(typed_target_profiles) != SUM_COMPONENT_COUNT:
                continue

            relation = infer_relation(source_transitions, target_transitions)
            if relation is None:
                continue

            candidates.append(
                ExpressionCorrespondenceCandidate(
                    source=EntityExpression(ExpressionKind.IDENTITY, (source_profile.entity,)),
                    target=EntityExpression(
                        ExpressionKind.SUM,
                        tuple(profile.entity for profile in typed_target_profiles),
                    ),
                    relation=relation,
                    evidence=[
                        Evidence(
                            kind=EvidenceKind.DYNAMIC_TRANSITION,
                            producer=PRODUCER,
                            family=EvidenceFamily.RUNTIME,
                            attributes={
                                "matched_pairs": len(pairs),
                                "total_pairs": len(pairs),
                                "distinct_transitions": _distinct_count(source_transitions),
                                "target_operator": ExpressionKind.SUM.value,
                                "target_component_count": SUM_COMPONENT_COUNT,
                            },
                        ),
                        build_schema_evidence(source_profile, typed_target_profiles),
                    ],
                )
            )

    return candidates


def _transitions_for(
    key: ObservationKey,
    observations: list[dict[ObservationKey, ObservedTransition]],
) -> list[ObservedTransition] | None:
    transitions: list[ObservedTransition] = []
    for values in observations:
        transition = values.get(key)
        if transition is None:
            return None
        transitions.append(transition)
    return transitions


def _summed_transitions(
    keys: tuple[ObservationKey, ...],
    observations: list[dict[ObservationKey, ObservedTransition]],
) -> list[ObservedTransition] | None:
    aggregated: list[ObservedTransition] = []
    for values in observations:
        components = [values.get(key) for key in keys]
        if any(component is None for component in components):
            return None

        typed_components = [component for component in components if component is not None]
        before_values = [to_decimal(component.before) for component in typed_components]
        after_values = [to_decimal(component.after) for component in typed_components]
        if any(value is None for value in before_values + after_values):
            return None

        aggregated.append(
            ObservedTransition(
                before=sum(value for value in before_values if value is not None),
                after=sum(value for value in after_values if value is not None),
            )
        )
    return aggregated


def _distinct_count(transitions: list[ObservedTransition]) -> int:
    return len({transition_fingerprint(transition) for transition in transitions})


def _profiles(
    keys: list[ObservationKey],
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
