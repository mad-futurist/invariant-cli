from dataclasses import dataclass
from enum import StrEnum

from invariant_cli.matching.model import EntityRef


class ValueType(StrEnum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    STRING = "string"
    OBJECT = "object"
    ARRAY = "array"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SchemaProfile:
    entity: EntityRef
    value_type: ValueType
    nullable: bool
    parent: str | None
    primary_key_context: bool
    name_tokens: tuple[str, ...]
    cardinality: int = 1
