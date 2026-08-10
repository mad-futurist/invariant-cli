import hashlib
import json

from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    CorrespondenceCandidate,
    EntityExpression,
    ExecutionPairRef,
    ExpressionCorrespondenceCandidate,
)
from invariant_cli.contracts.validation import ContractValidationResult
from invariant_cli.evidence.model import (
    EvidenceEdge,
    EvidenceEdgeKind,
    EvidenceGraph,
    EvidenceNode,
    EvidenceNodeKind,
)
from invariant_cli.matching.model import EntityRef, EvidenceKind
from invariant_cli.matching.transition import ObservedTransition
from invariant_cli.observation.model import serialize_value


def build_candidate_evidence_graph(contract: CandidateTranslationContract) -> EvidenceGraph:
    nodes: dict[str, EvidenceNode] = {}
    edges: list[EvidenceEdge] = []

    pair_ids: list[str] = []
    for pair in contract.paired_executions:
        pair_id = execution_pair_id(pair)
        pair_ids.append(pair_id)
        nodes[pair_id] = EvidenceNode(
            id=pair_id,
            kind=EvidenceNodeKind.EXECUTION_PAIR,
            attributes={
                "source_execution": pair.source_execution,
                "target_execution": pair.target_execution,
            },
        )

    for candidate in contract.correspondences:
        correspondence = correspondence_id(candidate)
        source = entity_id(candidate.source)
        target = entity_id(candidate.target)
        relation = relation_id(candidate)

        nodes[source] = _entity_node(source, candidate.source)
        nodes[target] = _entity_node(target, candidate.target)
        nodes[correspondence] = EvidenceNode(
            id=correspondence,
            kind=EvidenceNodeKind.CORRESPONDENCE,
        )
        nodes[relation] = EvidenceNode(
            id=relation,
            kind=EvidenceNodeKind.RELATION,
            attributes={
                "kind": candidate.relation.kind.value,
                "scale": candidate.relation.scale,
                "offset": candidate.relation.offset,
            },
        )
        edges.extend(
            [
                EvidenceEdge(correspondence, source, EvidenceEdgeKind.HAS_SOURCE),
                EvidenceEdge(correspondence, target, EvidenceEdgeKind.HAS_TARGET),
                EvidenceEdge(correspondence, relation, EvidenceEdgeKind.USES_RELATION),
            ]
        )

        for index, item in enumerate(candidate.evidence):
            evidence = evidence_id(candidate, index, item.kind.value, item.producer)
            nodes[evidence] = EvidenceNode(
                id=evidence,
                kind=EvidenceNodeKind.EVIDENCE,
                attributes={
                    "kind": item.kind.value,
                    "producer": item.producer,
                    **item.attributes,
                },
            )
            edges.append(EvidenceEdge(evidence, correspondence, EvidenceEdgeKind.SUPPORTS))

            if item.kind == EvidenceKind.DYNAMIC_TRANSITION:
                edges.extend(
                    EvidenceEdge(evidence, pair_id, EvidenceEdgeKind.DERIVED_FROM)
                    for pair_id in pair_ids
                )

    for expression_candidate in contract.expression_correspondences:
        correspondence = expression_correspondence_id(expression_candidate)
        source = expression_id(expression_candidate.source)
        target = expression_id(expression_candidate.target)
        relation = expression_relation_id(expression_candidate)

        _add_expression(nodes, edges, expression_candidate.source)
        _add_expression(nodes, edges, expression_candidate.target)
        nodes[correspondence] = EvidenceNode(
            id=correspondence,
            kind=EvidenceNodeKind.CORRESPONDENCE,
            attributes={"shape": "expression"},
        )
        nodes[relation] = EvidenceNode(
            id=relation,
            kind=EvidenceNodeKind.RELATION,
            attributes={
                "kind": expression_candidate.relation.kind.value,
                "scale": expression_candidate.relation.scale,
                "offset": expression_candidate.relation.offset,
            },
        )
        edges.extend(
            [
                EvidenceEdge(correspondence, source, EvidenceEdgeKind.HAS_SOURCE),
                EvidenceEdge(correspondence, target, EvidenceEdgeKind.HAS_TARGET),
                EvidenceEdge(correspondence, relation, EvidenceEdgeKind.USES_RELATION),
            ]
        )

        for index, item in enumerate(expression_candidate.evidence):
            evidence = expression_evidence_id(
                expression_candidate, index, item.kind.value, item.producer
            )
            nodes[evidence] = EvidenceNode(
                id=evidence,
                kind=EvidenceNodeKind.EVIDENCE,
                attributes={
                    "kind": item.kind.value,
                    "producer": item.producer,
                    **item.attributes,
                },
            )
            edges.append(EvidenceEdge(evidence, correspondence, EvidenceEdgeKind.SUPPORTS))
            if item.kind == EvidenceKind.DYNAMIC_TRANSITION:
                edges.extend(
                    EvidenceEdge(evidence, pair_id, EvidenceEdgeKind.DERIVED_FROM)
                    for pair_id in pair_ids
                )

    return _graph(nodes, edges)


def build_validation_evidence_graph(
    contract: CandidateTranslationContract,
    result: ContractValidationResult,
) -> EvidenceGraph:
    candidate_graph = build_candidate_evidence_graph(contract)
    nodes = {node.id: node for node in candidate_graph.nodes}
    edges = list(candidate_graph.edges)
    candidates = {
        (candidate.source, candidate.target): candidate for candidate in contract.correspondences
    }
    expression_candidates = {
        (candidate.source, candidate.target): candidate
        for candidate in contract.expression_correspondences
    }

    for pair_index, pair_result in enumerate(result.pairs):
        pair = validation_pair_id(pair_result.pair, pair_index)
        nodes[pair] = EvidenceNode(
            id=pair,
            kind=EvidenceNodeKind.VALIDATION_PAIR,
            attributes={
                "source_execution": pair_result.pair.source_execution,
                "target_execution": pair_result.pair.target_execution,
                "verdict": pair_result.verdict.value,
            },
        )

        for item_index, item in enumerate(pair_result.correspondences):
            validation = validation_id(pair, item_index, item.source, item.target)
            nodes[validation] = EvidenceNode(
                id=validation,
                kind=EvidenceNodeKind.VALIDATION,
                attributes={
                    "verdict": item.verdict.value,
                    "source_transition": _transition_data(item.source_transition),
                    "target_transition": _transition_data(item.target_transition),
                },
            )
            edges.append(EvidenceEdge(validation, pair, EvidenceEdgeKind.PART_OF))

            candidate = candidates.get((item.source, item.target))
            if candidate is not None:
                edges.append(
                    EvidenceEdge(
                        validation,
                        correspondence_id(candidate),
                        EvidenceEdgeKind.VALIDATES,
                    )
                )

        for item_index, expression_item in enumerate(pair_result.expression_correspondences):
            validation = expression_validation_id(
                pair, item_index, expression_item.source, expression_item.target
            )
            nodes[validation] = EvidenceNode(
                id=validation,
                kind=EvidenceNodeKind.VALIDATION,
                attributes={
                    "shape": "expression",
                    "verdict": expression_item.verdict.value,
                    "source_transition": _transition_data(expression_item.source_transition),
                    "target_transition": _transition_data(expression_item.target_transition),
                    "source_components": [
                        {
                            "entity": entity_id(component.entity),
                            "transition": _transition_data(component.transition),
                        }
                        for component in expression_item.source_components
                    ],
                    "target_components": [
                        {
                            "entity": entity_id(component.entity),
                            "transition": _transition_data(component.transition),
                        }
                        for component in expression_item.target_components
                    ],
                },
            )
            edges.append(EvidenceEdge(validation, pair, EvidenceEdgeKind.PART_OF))
            expression_candidate = expression_candidates.get(
                (expression_item.source, expression_item.target)
            )
            if expression_candidate is not None:
                edges.append(
                    EvidenceEdge(
                        validation,
                        expression_correspondence_id(expression_candidate),
                        EvidenceEdgeKind.VALIDATES,
                    )
                )

    return _graph(nodes, edges)


def entity_id(entity: EntityRef) -> str:
    return f"entity:{entity.kind.value}:{entity.namespace}#{entity.identifier}"


def correspondence_id(candidate: CorrespondenceCandidate) -> str:
    return "correspondence:" + _digest(
        {
            "source": entity_id(candidate.source),
            "target": entity_id(candidate.target),
            "relation": {
                "kind": candidate.relation.kind.value,
                "scale": candidate.relation.scale,
                "offset": candidate.relation.offset,
            },
        }
    )


def relation_id(candidate: CorrespondenceCandidate) -> str:
    return f"relation:{correspondence_id(candidate).removeprefix('correspondence:')}"


def expression_id(expression: EntityExpression) -> str:
    return "expression:" + _digest(
        {
            "kind": expression.kind.value,
            "components": [entity_id(component) for component in expression.components],
        }
    )


def expression_correspondence_id(candidate: ExpressionCorrespondenceCandidate) -> str:
    return "correspondence:" + _digest(
        {
            "source": expression_id(candidate.source),
            "target": expression_id(candidate.target),
            "relation": {
                "kind": candidate.relation.kind.value,
                "scale": candidate.relation.scale,
                "offset": candidate.relation.offset,
            },
        }
    )


def expression_relation_id(candidate: ExpressionCorrespondenceCandidate) -> str:
    digest = expression_correspondence_id(candidate).removeprefix("correspondence:")
    return f"relation:{digest}"


def execution_pair_id(pair: ExecutionPairRef) -> str:
    return "execution-pair:" + _digest(
        {"source": pair.source_execution, "target": pair.target_execution}
    )


def evidence_id(
    candidate: CorrespondenceCandidate,
    index: int,
    kind: str,
    producer: str,
) -> str:
    return "evidence:" + _digest(
        {
            "correspondence": correspondence_id(candidate),
            "index": index,
            "kind": kind,
            "producer": producer,
        }
    )


def expression_evidence_id(
    candidate: ExpressionCorrespondenceCandidate,
    index: int,
    kind: str,
    producer: str,
) -> str:
    return "evidence:" + _digest(
        {
            "correspondence": expression_correspondence_id(candidate),
            "index": index,
            "kind": kind,
            "producer": producer,
        }
    )


def validation_pair_id(pair: ExecutionPairRef, index: int) -> str:
    return "validation-pair:" + _digest(
        {
            "index": index,
            "source": pair.source_execution,
            "target": pair.target_execution,
        }
    )


def validation_id(pair_id: str, index: int, source: EntityRef, target: EntityRef) -> str:
    return "validation:" + _digest(
        {
            "pair": pair_id,
            "index": index,
            "source": entity_id(source),
            "target": entity_id(target),
        }
    )


def expression_validation_id(
    pair_id: str,
    index: int,
    source: EntityExpression,
    target: EntityExpression,
) -> str:
    return "validation:" + _digest(
        {
            "pair": pair_id,
            "index": index,
            "source": expression_id(source),
            "target": expression_id(target),
        }
    )


def _entity_node(node_id: str, entity: EntityRef) -> EvidenceNode:
    return EvidenceNode(
        id=node_id,
        kind=EvidenceNodeKind.ENTITY,
        attributes={
            "kind": entity.kind.value,
            "namespace": entity.namespace,
            "identifier": entity.identifier,
        },
    )


def _add_expression(
    nodes: dict[str, EvidenceNode],
    edges: list[EvidenceEdge],
    expression: EntityExpression,
) -> None:
    node_id = expression_id(expression)
    nodes[node_id] = EvidenceNode(
        id=node_id,
        kind=EvidenceNodeKind.EXPRESSION,
        attributes={"kind": expression.kind.value},
    )
    for index, component in enumerate(expression.components):
        component_id = entity_id(component)
        nodes[component_id] = _entity_node(component_id, component)
        edges.append(
            EvidenceEdge(
                node_id,
                component_id,
                EvidenceEdgeKind.HAS_COMPONENT,
                attributes={"position": index},
            )
        )


def _transition_data(transition: ObservedTransition | None) -> object:
    if transition is None:
        return None
    return {
        "before": serialize_value(transition.before),
        "after": serialize_value(transition.after),
    }


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _graph(nodes: dict[str, EvidenceNode], edges: list[EvidenceEdge]) -> EvidenceGraph:
    unique_edges = {(edge.source, edge.target, edge.kind.value): edge for edge in edges}
    return EvidenceGraph(
        version=2,
        nodes=sorted(nodes.values(), key=lambda node: node.id),
        edges=sorted(
            unique_edges.values(),
            key=lambda edge: (edge.source, edge.target, edge.kind.value),
        ),
    )
