from dataclasses import dataclass, field
from enum import StrEnum


class EvidenceNodeKind(StrEnum):
    CANDIDATE_SET = "candidate_set"
    ENTITY = "entity"
    CORRESPONDENCE = "correspondence"
    RELATION = "relation"
    EVIDENCE = "evidence"
    EXECUTION_PAIR = "execution_pair"
    VALIDATION_PAIR = "validation_pair"
    VALIDATION = "validation"
    EXPRESSION = "expression"


class EvidenceEdgeKind(StrEnum):
    CONTAINS = "contains"
    HAS_SOURCE = "has_source"
    HAS_TARGET = "has_target"
    USES_RELATION = "uses_relation"
    SUPPORTS = "supports"
    DERIVED_FROM = "derived_from"
    VALIDATES = "validates"
    PART_OF = "part_of"
    HAS_COMPONENT = "has_component"


@dataclass(frozen=True)
class EvidenceNode:
    id: str
    kind: EvidenceNodeKind
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceEdge:
    source: str
    target: str
    kind: EvidenceEdgeKind
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceGraph:
    version: int
    nodes: list[EvidenceNode]
    edges: list[EvidenceEdge]


def evidence_graph_to_data(graph: EvidenceGraph) -> dict[str, object]:
    return {
        "version": graph.version,
        "nodes": [
            {
                "id": node.id,
                "kind": node.kind.value,
                "attributes": node.attributes,
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "kind": edge.kind.value,
                "attributes": edge.attributes,
            }
            for edge in graph.edges
        ],
    }
