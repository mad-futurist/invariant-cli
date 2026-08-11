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


class FlowNodeKind(StrEnum):
    FIELD_READ = "field_read"
    VARIABLE = "variable"
    OPERATION = "operation"
    CALL = "call"
    FIELD_WRITE = "field_write"


class FlowEdgeKind(StrEnum):
    READS_INTO = "reads_into"
    FLOWS_TO = "flows_to"
    ARGUMENT_TO = "argument_to"
    WRITES_TO = "writes_to"


@dataclass(frozen=True)
class FunctionRef:
    module: str
    name: str


@dataclass(frozen=True)
class FlowNode:
    id: str
    kind: str
    label: str


@dataclass(frozen=True)
class FlowEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class FunctionFlow:
    function: FunctionRef
    nodes: list[FlowNode]
    edges: list[FlowEdge]
