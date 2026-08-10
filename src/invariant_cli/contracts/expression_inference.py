from itertools import combinations

from invariant_cli.contracts.model import (
    EntityExpression,
    ExpressionCorrespondenceCandidate,
    ExpressionKind,
)
from invariant_cli.contracts.relations import infer_relation, to_decimal
from invariant_cli.matching.model import EntityKind, EntityRef, Evidence, EvidenceKind
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
) -> list[ExpressionCorrespondenceCandidate]:
    """Infer one source entity against the sum of exactly two target entities."""
    if not pairs:
        return []

    flattened_pairs = [
        (flatten_observations(source), flatten_observations(target)) for source, target in pairs
    ]
    source_keys = sorted({key for source, _ in flattened_pairs for key in source})
    target_keys = sorted({key for _, target in flattened_pairs for key in target})
    candidates: list[ExpressionCorrespondenceCandidate] = []

    for source_key in source_keys:
        source_transitions = _transitions_for(source_key, [source for source, _ in flattened_pairs])
        if source_transitions is None or _distinct_count(source_transitions) < 2:
            continue

        source_entity = _entity_ref(source_key)
        if source_entity is None:
            continue

        for target_key_pair in combinations(target_keys, SUM_COMPONENT_COUNT):
            target_transitions = _summed_transitions(
                target_key_pair,
                [target for _, target in flattened_pairs],
            )
            if target_transitions is None:
                continue

            target_entities = tuple(_entity_ref(key) for key in target_key_pair)
            if any(entity is None for entity in target_entities):
                continue

            relation = infer_relation(source_transitions, target_transitions)
            if relation is None:
                continue

            typed_targets = tuple(entity for entity in target_entities if entity is not None)
            candidates.append(
                ExpressionCorrespondenceCandidate(
                    source=EntityExpression(ExpressionKind.IDENTITY, (source_entity,)),
                    target=EntityExpression(ExpressionKind.SUM, typed_targets),
                    relation=relation,
                    evidence=[
                        Evidence(
                            kind=EvidenceKind.DYNAMIC_TRANSITION,
                            producer=PRODUCER,
                            attributes={
                                "matched_pairs": len(pairs),
                                "total_pairs": len(pairs),
                                "distinct_transitions": _distinct_count(source_transitions),
                                "target_operator": ExpressionKind.SUM.value,
                                "target_component_count": SUM_COMPONENT_COUNT,
                            },
                        )
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


def _entity_ref(key: ObservationKey) -> EntityRef | None:
    observation_kind, namespace, identifier = key
    kinds = {
        "json": EntityKind.JSON_FIELD,
        "sqlite": EntityKind.SQLITE_FIELD,
    }
    kind = kinds.get(observation_kind)
    if kind is None:
        return None
    return EntityRef(kind=kind, namespace=namespace, identifier=identifier)
