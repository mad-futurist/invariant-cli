from decimal import Decimal

from invariant_cli.contracts.model import RelationKind
from invariant_cli.contracts.relations import apply_relation, infer_relation
from invariant_cli.matching.transition import ObservedTransition


def test_infers_exact_relation() -> None:
    source = [
        ObservedTransition(before=100, after=70),
        ObservedTransition(before=200, after=150),
    ]

    target = [
        ObservedTransition(before=100, after=70),
        ObservedTransition(before=200, after=150),
    ]

    relation = infer_relation(source, target)

    assert relation is not None
    assert relation.kind == RelationKind.EXACT


def test_infers_affine_relation() -> None:
    source = [
        ObservedTransition(before=10000, after=7000),
        ObservedTransition(before=10000, after=4000),
        ObservedTransition(before=25000, after=19000),
    ]

    target = [
        ObservedTransition(before=100, after=70),
        ObservedTransition(before=100, after=40),
        ObservedTransition(before=250, after=190),
    ]

    relation = infer_relation(source, target)

    assert relation is not None
    assert relation.kind == RelationKind.AFFINE
    assert relation.scale == "0.01"
    assert relation.offset == "0"

    assert apply_relation(relation, 22500) == Decimal("225")


def test_bool_does_not_match_integer() -> None:
    source = [
        ObservedTransition(before=False, after=True),
        ObservedTransition(before=True, after=False),
    ]

    target = [
        ObservedTransition(before=0, after=1),
        ObservedTransition(before=1, after=0),
    ]

    assert infer_relation(source, target) is None
