from invariant_cli.matching.model import Evidence, EvidenceKind
from invariant_cli.matching.static.model import FieldUsage

PRODUCER = "python-ast-v1"


def compare_usage(source: FieldUsage, target: FieldUsage) -> dict[str, object]:
    common = source.operations & target.operations

    return {
        "source_operations": sorted(operation.value for operation in source.operations),
        "target_operations": sorted(operation.value for operation in target.operations),
        "common_operations": sorted(operation.value for operation in common),
    }


def build_static_usage_evidence(source: FieldUsage, target: FieldUsage) -> Evidence | None:
    common = source.operations & target.operations

    if not common:
        return None

    return Evidence(
        kind=EvidenceKind.STATIC_USAGE,
        producer=PRODUCER,
        attributes=compare_usage(source, target),
    )
