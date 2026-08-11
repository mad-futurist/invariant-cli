import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from invariant_cli.matching.model import (
    EntityKind,
    EntityRef,
    Evidence,
    EvidenceFamily,
    EvidenceKind,
)
from invariant_cli.matching.schema.model import SchemaProfile, ValueType
from invariant_cli.matching.transition import ObservationKey, ObservedTransition
from invariant_cli.observation.model import ABSENT

PRODUCER = "observed-schema-v1"


def entity_ref(key: ObservationKey) -> EntityRef | None:
    observation_kind, namespace, identifier = key
    kinds = {
        "json": EntityKind.JSON_FIELD,
        "sqlite": EntityKind.SQLITE_FIELD,
    }
    kind = kinds.get(observation_kind)
    if kind is None:
        return None
    return EntityRef(kind=kind, namespace=namespace, identifier=identifier)


def profile_observed_field(
    key: ObservationKey,
    transitions: Iterable[ObservedTransition],
) -> SchemaProfile | None:
    entity = entity_ref(key)
    if entity is None:
        return None

    values: list[Any] = []
    for transition in transitions:
        values.extend((transition.before, transition.after))

    return SchemaProfile(
        entity=entity,
        value_type=_value_type(values),
        nullable=any(value is None for value in values),
        parent=_parent(entity.identifier),
        primary_key_context=(
            entity.kind == EntityKind.SQLITE_FIELD
            and bool(re.search(r"\[[^\]]+=[^\]]+\]", entity.identifier))
        ),
        name_tokens=_name_tokens(entity.identifier),
    )


def profiles_compatible(source: SchemaProfile, target: SchemaProfile) -> bool:
    unknown = {ValueType.UNKNOWN, ValueType.MIXED}
    return (
        source.value_type in unknown
        or target.value_type in unknown
        or source.value_type == target.value_type
    )


def share_structural_scope(left: SchemaProfile, right: SchemaProfile) -> bool:
    return (
        left.entity.kind == right.entity.kind
        and left.entity.namespace == right.entity.namespace
        and left.parent == right.parent
    )


def build_schema_evidence(
    source: SchemaProfile,
    targets: tuple[SchemaProfile, ...],
) -> Evidence:
    target_types = sorted({target.value_type.value for target in targets})
    target_type = target_types[0] if len(target_types) == 1 else ValueType.MIXED.value
    target_tokens = sorted({token for target in targets for token in target.name_tokens})
    common_tokens = sorted(set(source.name_tokens) & set(target_tokens))
    target_parents = sorted({target.parent for target in targets if target.parent is not None})
    target_parent: object
    if not target_parents:
        target_parent = None
    elif len(target_parents) == 1:
        target_parent = target_parents[0]
    else:
        target_parent = target_parents
    structural_scope_compatible = len(targets) == 1 or all(
        share_structural_scope(targets[0], target) for target in targets[1:]
    )

    return Evidence(
        kind=EvidenceKind.SCHEMA,
        producer=PRODUCER,
        family=EvidenceFamily.OBSERVED_SCHEMA,
        attributes={
            "source_type": source.value_type.value,
            "target_type": target_type,
            "type_compatible": all(profiles_compatible(source, target) for target in targets),
            "source_parent": source.parent,
            "target_parent": target_parent,
            "source_nullable": source.nullable,
            "target_nullable": any(target.nullable for target in targets),
            "source_cardinality": source.cardinality,
            "target_cardinality": sum(target.cardinality for target in targets),
            "source_primary_key_context": source.primary_key_context,
            "target_primary_key_context": any(target.primary_key_context for target in targets),
            "source_name_tokens": list(source.name_tokens),
            "target_name_tokens": target_tokens,
            "common_name_tokens": common_tokens,
            "structural_scope_compatible": structural_scope_compatible,
        },
    )


def blocking_priority(
    source: SchemaProfile,
    targets: tuple[SchemaProfile, ...],
) -> tuple[object, ...]:
    target_tokens = {token for target in targets for token in target.name_tokens}
    common_tokens = len(set(source.name_tokens) & target_tokens)
    exact_type = all(source.value_type == target.value_type for target in targets)
    return (
        -common_tokens,
        -int(exact_type),
        tuple(target.entity.locator for target in targets),
    )


def _value_type(values: Iterable[Any]) -> ValueType:
    types = {
        _single_value_type(value) for value in values if value is not None and value is not ABSENT
    }
    if not types:
        return ValueType.UNKNOWN
    if len(types) == 1:
        return types.pop()
    return ValueType.MIXED


def _single_value_type(value: Any) -> ValueType:
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    if isinstance(value, (int, float, Decimal)):
        return ValueType.NUMBER
    if isinstance(value, str):
        return ValueType.STRING
    if isinstance(value, dict):
        return ValueType.OBJECT
    if isinstance(value, list):
        return ValueType.ARRAY
    return ValueType.UNKNOWN


def _parent(identifier: str) -> str | None:
    if "." not in identifier:
        return None
    return identifier.rsplit(".", 1)[0]


def _name_tokens(identifier: str) -> tuple[str, ...]:
    field_name = identifier.rsplit(".", 1)[-1]
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", field_name)
    return tuple(sorted({token.lower() for token in re.split(r"[^A-Za-z0-9]+", parts) if token}))
