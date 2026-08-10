from invariant_cli.contracts.inference import infer_correspondences
from invariant_cli.contracts.model import Relation, RelationKind
from invariant_cli.matching.model import EvidenceKind
from invariant_cli.observation.model import (
    Observation,
    ValueChange,
)


def observation(
    resource: str,
    path: str,
    before: object,
    after: object,
) -> Observation:
    return Observation(
        source=resource,
        kind="json",
        changes=[
            ValueChange(
                path=path,
                before=before,
                after=after,
            )
        ],
    )


def test_infers_correspondence_from_transitions() -> None:
    pairs = [
        (
            [
                observation(
                    "state.json",
                    "balance",
                    100,
                    70,
                )
            ],
            [
                observation(
                    "account.json",
                    "remaining",
                    100,
                    70,
                )
            ],
        ),
        (
            [
                observation(
                    "state.json",
                    "balance",
                    100,
                    40,
                )
            ],
            [
                observation(
                    "account.json",
                    "remaining",
                    100,
                    40,
                )
            ],
        ),
        (
            [
                observation(
                    "state.json",
                    "balance",
                    250,
                    190,
                )
            ],
            [
                observation(
                    "account.json",
                    "remaining",
                    250,
                    190,
                )
            ],
        ),
    ]

    candidates = infer_correspondences(pairs)

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.source.namespace == "state.json"
    assert candidate.source.identifier == "balance"

    assert candidate.target.namespace == "account.json"
    assert candidate.target.identifier == "remaining"

    dyn = next(e for e in candidate.evidence if e.kind == EvidenceKind.DYNAMIC_TRANSITION)
    assert dyn.attributes["matched_pairs"] == 3
    assert dyn.attributes["total_pairs"] == 3
    assert dyn.attributes["distinct_transitions"] == 3
    assert candidate.relation == Relation(kind=RelationKind.EXACT)


def test_does_not_infer_inconsistent_correspondence() -> None:
    pairs = [
        (
            [
                observation(
                    "state.json",
                    "balance",
                    100,
                    70,
                )
            ],
            [
                observation(
                    "account.json",
                    "remaining",
                    100,
                    70,
                )
            ],
        ),
        (
            [
                observation(
                    "state.json",
                    "balance",
                    100,
                    40,
                )
            ],
            [
                observation(
                    "account.json",
                    "remaining",
                    100,
                    50,  # diverges from source
                )
            ],
        ),
        (
            [
                observation(
                    "state.json",
                    "balance",
                    250,
                    190,
                )
            ],
            [
                observation(
                    "account.json",
                    "remaining",
                    250,
                    190,
                )
            ],
        ),
    ]

    candidates = infer_correspondences(pairs)

    assert candidates == []


def test_does_not_infer_from_repeated_constant_transition() -> None:
    pairs = [
        (
            [
                observation(
                    "state.json",
                    "status",
                    "pending",
                    "active",
                )
            ],
            [
                observation(
                    "account.json",
                    "state",
                    "pending",
                    "active",
                )
            ],
        ),
        (
            [
                observation(
                    "state.json",
                    "status",
                    "pending",
                    "active",
                )
            ],
            [
                observation(
                    "account.json",
                    "state",
                    "pending",
                    "active",
                )
            ],
        ),
        (
            [
                observation(
                    "state.json",
                    "status",
                    "pending",
                    "active",
                )
            ],
            [
                observation(
                    "account.json",
                    "state",
                    "pending",
                    "active",
                )
            ],
        ),
    ]

    candidates = infer_correspondences(pairs)

    assert candidates == []


def test_preserves_ambiguous_candidates() -> None:
    pairs = []

    transitions = [
        (100, 70),
        (100, 40),
        (250, 190),
    ]

    for before, after in transitions:
        source = [
            observation(
                "state.json",
                "balance",
                before,
                after,
            )
        ]

        target = [
            Observation(
                source="account.json",
                kind="json",
                changes=[
                    ValueChange(
                        path="remaining",
                        before=before,
                        after=after,
                    ),
                    ValueChange(
                        path="total",
                        before=before,
                        after=after,
                    ),
                ],
            )
        ]

        pairs.append((source, target))

    candidates = infer_correspondences(pairs)

    assert len(candidates) == 2

    target_paths = {candidate.target.identifier for candidate in candidates}

    assert target_paths == {"remaining", "total"}
