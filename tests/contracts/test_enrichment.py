from invariant_cli.contracts.enrichment import enrich_with_static_usage
from invariant_cli.contracts.model import CorrespondenceCandidate, Relation, RelationKind
from invariant_cli.matching.model import (
    EntityKind,
    EntityRef,
    Evidence,
    EvidenceFamily,
    EvidenceKind,
)
from invariant_cli.matching.static.model import FieldUsage, UsageOperation


def candidate() -> CorrespondenceCandidate:
    return CorrespondenceCandidate(
        source=EntityRef(
            kind=EntityKind.JSON_FIELD,
            namespace="state.json",
            identifier="balance_cents",
        ),
        target=EntityRef(
            kind=EntityKind.JSON_FIELD,
            namespace="account.json",
            identifier="remaining",
        ),
        relation=Relation(
            kind=RelationKind.AFFINE,
            scale="0.01",
        ),
        evidence=[
            Evidence(
                kind=EvidenceKind.DYNAMIC_TRANSITION,
                producer="dynamic-transition-v1",
                family=EvidenceFamily.RUNTIME,
            )
        ],
    )


def test_adds_static_usage_to_dynamic_candidate() -> None:
    result = enrich_with_static_usage(
        [candidate()],
        {
            "balance_cents": FieldUsage(
                identifier="balance_cents",
                operations={
                    UsageOperation.READ,
                    UsageOperation.WRITE,
                    UsageOperation.SUBTRACT,
                },
            )
        },
        {
            "remaining": FieldUsage(
                identifier="remaining",
                operations={
                    UsageOperation.READ,
                    UsageOperation.WRITE,
                    UsageOperation.SUBTRACT,
                },
            )
        },
    )

    assert len(result) == 1
    assert len(result[0].evidence) == 2

    static = result[0].evidence[1]
    assert static.kind == EvidenceKind.STATIC_USAGE
    assert static.producer == "python-ast-v1"
    assert static.attributes == {
        "source_operations": ["read", "subtract", "write"],
        "target_operations": ["read", "subtract", "write"],
        "common_operations": ["read", "subtract", "write"],
    }


def test_keeps_candidate_without_static_evidence_when_usage_does_not_overlap() -> None:
    original = candidate()

    result = enrich_with_static_usage(
        [original],
        {
            "balance_cents": FieldUsage(
                identifier="balance_cents",
                operations={UsageOperation.READ},
            )
        },
        {
            "remaining": FieldUsage(
                identifier="remaining",
                operations={UsageOperation.WRITE},
            )
        },
    )

    assert result == [original]
