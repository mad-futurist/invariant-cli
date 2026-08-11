from dataclasses import dataclass
from itertools import combinations

from invariant_cli.matching.schema.model import SchemaProfile, ValueType
from invariant_cli.matching.schema.observed import (
    blocking_priority,
    profiles_compatible,
    share_structural_scope,
)
from invariant_cli.matching.transition import ObservationKey


@dataclass(frozen=True)
class InferenceLimits:
    max_direct_targets_per_source: int = 50
    max_expression_pairs_per_source: int = 100

    def __post_init__(self) -> None:
        if self.max_direct_targets_per_source < 1:
            raise ValueError("max_direct_targets_per_source must be positive.")
        if self.max_expression_pairs_per_source < 1:
            raise ValueError("max_expression_pairs_per_source must be positive.")


def shortlist_direct_targets(
    source: SchemaProfile,
    targets: dict[ObservationKey, SchemaProfile],
    *,
    limit: int,
) -> list[ObservationKey]:
    compatible = [
        (key, profile) for key, profile in targets.items() if profiles_compatible(source, profile)
    ]
    compatible.sort(key=lambda item: blocking_priority(source, (item[1],)))
    return [key for key, _ in compatible[:limit]]


def shortlist_expression_targets(
    source: SchemaProfile,
    targets: dict[ObservationKey, SchemaProfile],
    *,
    component_count: int,
    limit: int,
) -> list[tuple[ObservationKey, ...]]:
    if source.value_type != ValueType.NUMBER:
        return []

    numeric = [
        (key, profile)
        for key, profile in targets.items()
        if profile.value_type == ValueType.NUMBER and profiles_compatible(source, profile)
    ]
    profile_by_key = dict(numeric)
    candidates = [
        keys
        for keys in combinations(sorted(profile_by_key), component_count)
        if all(
            share_structural_scope(profile_by_key[keys[0]], profile_by_key[key]) for key in keys[1:]
        )
    ]
    candidates.sort(
        key=lambda keys: blocking_priority(
            source,
            tuple(profile_by_key[key] for key in keys),
        )
    )
    return candidates[:limit]
