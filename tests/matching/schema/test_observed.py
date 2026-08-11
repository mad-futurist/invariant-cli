from invariant_cli.matching.model import EvidenceKind
from invariant_cli.matching.schema.model import ValueType
from invariant_cli.matching.schema.observed import (
    build_schema_evidence,
    profile_observed_field,
    profiles_compatible,
)
from invariant_cli.matching.transition import ObservedTransition


def test_profiles_sqlite_field_and_builds_schema_evidence() -> None:
    source = profile_observed_field(
        ("sqlite", "legacy.db", "wallets[id=1].balance_cents"),
        [ObservedTransition(10000, 7000), ObservedTransition(10000, 4000)],
    )
    target = profile_observed_field(
        ("json", "account.json", "remaining_eur"),
        [ObservedTransition(100, 70), ObservedTransition(100, 40)],
    )

    assert source is not None
    assert target is not None
    assert source.value_type == ValueType.NUMBER
    assert source.parent == "wallets[id=1]"
    assert source.primary_key_context is True
    assert source.name_tokens == ("balance", "cents")
    assert profiles_compatible(source, target)

    evidence = build_schema_evidence(source, (target,))
    assert evidence.kind == EvidenceKind.SCHEMA
    assert evidence.producer == "observed-schema-v1"
    assert evidence.attributes["source_type"] == "number"
    assert evidence.attributes["target_type"] == "number"
    assert evidence.attributes["target_parent"] is None
    assert evidence.attributes["source_cardinality"] == 1
    assert evidence.attributes["target_cardinality"] == 1


def test_rejects_incompatible_boolean_and_numeric_profiles() -> None:
    source = profile_observed_field(
        ("json", "source.json", "enabled"),
        [ObservedTransition(False, True)],
    )
    target = profile_observed_field(
        ("json", "target.json", "count"),
        [ObservedTransition(0, 1)],
    )

    assert source is not None
    assert target is not None
    assert not profiles_compatible(source, target)
