from dataclasses import dataclass, field
from enum import StrEnum


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"


class CallResolutionKind(StrEnum):
    EXACT = "exact"
    HEURISTIC = "heuristic"
    AMBIGUOUS = "ambiguous"
    EXTERNAL = "external"


class SemanticNodeKind(StrEnum):
    PARAMETER = "parameter"
    VALUE = "value"
    STATE_READ = "state_read"
    STATE_WRITE = "state_write"
    OPERATION = "operation"
    CALL = "call"
    RETURN = "return"


class SemanticEdgeKind(StrEnum):
    FLOWS_TO = "flows_to"
    ARGUMENT_TO = "argument_to"
    RETURNS_TO = "returns_to"


class SemanticTerminalKind(StrEnum):
    STATE_WRITE = "state_write"
    RETURN = "return"
    EXTERNAL_CALL = "external_call"
    NONE = "none"


@dataclass(frozen=True)
class SemanticFunction:
    id: str
    module: str
    name: str
    parameters: tuple[str, ...]
    resolution: ResolutionStatus


@dataclass(frozen=True)
class SemanticNode:
    id: str
    function_id: str
    kind: SemanticNodeKind
    label: str


@dataclass(frozen=True)
class SemanticEdge:
    source: str
    target: str
    kind: SemanticEdgeKind
    argument_slot: int | None = None


@dataclass(frozen=True)
class SemanticCallResolution:
    call_node_id: str
    kind: CallResolutionKind
    target_function_id: str | None = None
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgramSemanticModel:
    functions: dict[str, SemanticFunction]
    nodes: list[SemanticNode]
    edges: list[SemanticEdge]
    call_resolutions: dict[str, SemanticCallResolution] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    def function_nodes(self, function_id: str) -> list[SemanticNode]:
        return [node for node in self.nodes if node.function_id == function_id]
