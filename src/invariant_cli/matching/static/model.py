from dataclasses import dataclass, field
from enum import StrEnum


class UsageOperation(StrEnum):
    READ = "read"
    WRITE = "write"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    COMPARE = "compare"


@dataclass(frozen=True)
class FieldUsage:
    identifier: str
    operations: set[UsageOperation] = field(default_factory=set)
