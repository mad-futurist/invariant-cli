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
    PARAMETER = "parameter"
    VARIABLE = "variable"
    OPERATION = "operation"
    CALL = "call"
    FIELD_WRITE = "field_write"
    RETURN = "return"


class FlowEdgeKind(StrEnum):
    READS_INTO = "reads_into"
    FLOWS_TO = "flows_to"
    ARGUMENT_TO = "argument_to"
    WRITES_TO = "writes_to"


class AnalysisResolution(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    DEPTH_LIMIT = "depth_limit"


class FlowTerminalKind(StrEnum):
    FIELD_WRITE = "field_write"
    RETURN = "return"
    EXTERNAL_CALL = "external_call"
    NONE = "none"


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
    argument_slot: int | None = None


@dataclass(frozen=True)
class FunctionFlow:
    function: FunctionRef
    parameters: tuple[str, ...]
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    resolution: AnalysisResolution = AnalysisResolution.RESOLVED
