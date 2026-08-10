from decimal import Decimal, InvalidOperation
from typing import Any

from invariant_cli.contracts.model import Relation, RelationKind
from invariant_cli.matching.transition import ObservedTransition, values_equal


def infer_relation(
    source: list[ObservedTransition],
    target: list[ObservedTransition],
) -> Relation | None:
    exact = _infer_exact(source, target)
    if exact is not None:
        return exact

    affine = _infer_affine(source, target)
    if affine is not None:
        return affine

    return None


def apply_relation(relation: Relation, value: Any) -> Any:
    if relation.kind == RelationKind.EXACT:
        return value

    if relation.kind == RelationKind.AFFINE:
        numeric = to_decimal(value)
        if numeric is None:
            return None

        scale = Decimal(relation.scale)
        offset = Decimal(relation.offset)

        return numeric * scale + offset

    raise ValueError(f"Unsupported relation: {relation.kind}")


def to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, Decimal)):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _infer_exact(
    source: list[ObservedTransition],
    target: list[ObservedTransition],
) -> Relation | None:
    for source_t, target_t in zip(source, target, strict=True):
        if not values_equal(source_t.before, target_t.before):
            return None
        if not values_equal(source_t.after, target_t.after):
            return None

    return Relation(kind=RelationKind.EXACT)


def _infer_affine(
    source: list[ObservedTransition],
    target: list[ObservedTransition],
) -> Relation | None:
    points: list[tuple[Decimal, Decimal]] = []

    for source_t, target_t in zip(source, target, strict=True):
        s_before = to_decimal(source_t.before)
        t_before = to_decimal(target_t.before)
        s_after = to_decimal(source_t.after)
        t_after = to_decimal(target_t.after)

        if s_before is None or t_before is None or s_after is None or t_after is None:
            return None

        points.append((s_before, t_before))
        points.append((s_after, t_after))

    unique_points = list(dict.fromkeys(points))

    if len(unique_points) < 2:
        return None

    first_x, first_y = unique_points[0]

    second_point = next(
        (point for point in unique_points[1:] if point[0] != first_x),
        None,
    )

    if second_point is None:
        return None

    second_x, second_y = second_point

    scale = (second_y - first_y) / (second_x - first_x)
    offset = first_y - first_x * scale

    for x, y in unique_points:
        if x * scale + offset != y:
            return None

    return Relation(
        kind=RelationKind.AFFINE,
        scale=_decimal_str(scale),
        offset=_decimal_str(offset),
    )


def _decimal_str(value: Decimal) -> str:
    return format(value.normalize(), "f")
