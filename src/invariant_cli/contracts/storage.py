import json
from pathlib import Path
from uuid import uuid4

import yaml

from invariant_cli.contracts.model import (
    CandidateHypothesis,
    CandidateSet,
    CandidateSetStatus,
    CandidateShape,
    CandidateTranslationContract,
    CorrespondenceCandidate,
    EntityExpression,
    ExecutionPairRef,
    ExpressionCorrespondenceCandidate,
    ExpressionKind,
    RankedCandidate,
    Relation,
    RelationKind,
)
from invariant_cli.contracts.validation import (
    ContractValidationResult,
    ExpressionComponentValidation,
)
from invariant_cli.evidence.builder import (
    build_candidate_evidence_graph,
    build_validation_evidence_graph,
    correspondence_id,
    expression_correspondence_id,
)
from invariant_cli.evidence.model import evidence_graph_to_data
from invariant_cli.matching.model import (
    EntityKind,
    EntityRef,
    Evidence,
    EvidenceKind,
)
from invariant_cli.matching.transition import ObservedTransition
from invariant_cli.observation.model import serialize_value


def save_candidate_contract(
    contract: CandidateTranslationContract,
    *,
    directory: Path,
) -> Path:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    contract_id = str(uuid4())

    output_path = directory / f"{contract_id}.candidate.yaml"

    data = {
        "id": contract_id,
        "version": contract.version,
        "status": "candidate",
        "paired_executions": [
            {
                "source": pair.source_execution,
                "target": pair.target_execution,
            }
            for pair in contract.paired_executions
        ],
        "correspondences": [
            {
                "source": {
                    "kind": candidate.source.kind.value,
                    "namespace": candidate.source.namespace,
                    "identifier": candidate.source.identifier,
                },
                "target": {
                    "kind": candidate.target.kind.value,
                    "namespace": candidate.target.namespace,
                    "identifier": candidate.target.identifier,
                },
                "relation": {
                    "kind": candidate.relation.kind.value,
                    "scale": candidate.relation.scale,
                    "offset": candidate.relation.offset,
                },
                "evidence": [
                    {
                        "kind": ev.kind.value,
                        "producer": ev.producer,
                        "attributes": ev.attributes,
                    }
                    for ev in candidate.evidence
                ],
            }
            for candidate in contract.correspondences
        ],
        "expression_correspondences": [
            {
                "source": _expression_to_data(candidate.source),
                "target": _expression_to_data(candidate.target),
                "relation": {
                    "kind": candidate.relation.kind.value,
                    "scale": candidate.relation.scale,
                    "offset": candidate.relation.offset,
                },
                "evidence": [
                    {
                        "kind": item.kind.value,
                        "producer": item.producer,
                        "attributes": item.attributes,
                    }
                    for item in candidate.evidence
                ],
            }
            for candidate in contract.expression_correspondences
        ],
        "candidate_sets": [
            _candidate_set_to_data(
                candidate_set,
                contract.correspondences,
                contract.expression_correspondences,
            )
            for candidate_set in contract.candidate_sets
        ],
        "evidence_graph": evidence_graph_to_data(build_candidate_evidence_graph(contract)),
    }

    output_path.write_text(
        yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    return output_path


def load_candidate_contract(path: Path) -> CandidateTranslationContract:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    paired_executions = [
        ExecutionPairRef(
            source_execution=pair["source"],
            target_execution=pair["target"],
        )
        for pair in data.get("paired_executions", [])
    ]

    correspondences: list[CorrespondenceCandidate] = []

    for entry in data.get("correspondences", []):
        src = entry["source"]
        tgt = entry["target"]
        rel = entry.get("relation", {})

        correspondences.append(
            CorrespondenceCandidate(
                source=EntityRef(
                    kind=EntityKind(src.get("kind", "json_field")),
                    namespace=src["namespace"],
                    identifier=src["identifier"],
                ),
                target=EntityRef(
                    kind=EntityKind(tgt.get("kind", "json_field")),
                    namespace=tgt["namespace"],
                    identifier=tgt["identifier"],
                ),
                relation=Relation(
                    kind=RelationKind(rel.get("kind", "exact")),
                    scale=str(rel.get("scale", "1")),
                    offset=str(rel.get("offset", "0")),
                ),
                evidence=[
                    Evidence(
                        kind=EvidenceKind(ev["kind"]),
                        producer=ev["producer"],
                        attributes=ev.get("attributes", {}),
                    )
                    for ev in entry.get("evidence", [])
                ],
            )
        )

    expression_correspondences: list[ExpressionCorrespondenceCandidate] = []
    for entry in data.get("expression_correspondences", []):
        rel = entry.get("relation", {})
        expression_correspondences.append(
            ExpressionCorrespondenceCandidate(
                source=_load_expression(entry["source"]),
                target=_load_expression(entry["target"]),
                relation=Relation(
                    kind=RelationKind(rel.get("kind", "exact")),
                    scale=str(rel.get("scale", "1")),
                    offset=str(rel.get("offset", "0")),
                ),
                evidence=[
                    Evidence(
                        kind=EvidenceKind(item["kind"]),
                        producer=item["producer"],
                        attributes=item.get("attributes", {}),
                    )
                    for item in entry.get("evidence", [])
                ],
            )
        )

    candidate_sets: list[CandidateSet] = []
    field_candidates_by_id = {
        correspondence_id(candidate): candidate for candidate in correspondences
    }
    expression_candidates_by_id = {
        expression_correspondence_id(candidate): candidate
        for candidate in expression_correspondences
    }
    for entry in data.get("candidate_sets", []):
        ranked_candidates: list[RankedCandidate] = []
        for ranked in entry.get("candidates", []):
            shape = CandidateShape(ranked["shape"])
            reference = str(ranked["correspondence"])
            candidate_hypothesis: CandidateHypothesis
            if shape == CandidateShape.FIELD:
                candidate_hypothesis = field_candidates_by_id[reference]
            else:
                candidate_hypothesis = expression_candidates_by_id[reference]
            ranked_candidates.append(
                RankedCandidate(
                    shape=shape,
                    rank=int(ranked["rank"]),
                    score=int(ranked["score"]),
                    factors={
                        str(name): int(value) for name, value in ranked.get("factors", {}).items()
                    },
                    candidate=candidate_hypothesis,
                )
            )
        candidate_sets.append(
            CandidateSet(
                source=_load_entity(entry["source"]),
                status=CandidateSetStatus(entry["status"]),
                candidates=ranked_candidates,
            )
        )

    return CandidateTranslationContract(
        version=data["version"],
        paired_executions=paired_executions,
        correspondences=correspondences,
        expression_correspondences=expression_correspondences,
        candidate_sets=candidate_sets,
    )


def save_contract_validation(
    result: ContractValidationResult,
    *,
    contract: CandidateTranslationContract,
    directory: Path,
    contract_path: Path,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    validation_id = str(uuid4())
    output_path = directory / f"{validation_id}.contract-validation.json"

    data = {
        "id": validation_id,
        "contract": str(contract_path),
        "verdict": result.verdict.value,
        "pairs": [
            {
                "source_execution": pair.pair.source_execution,
                "target_execution": pair.pair.target_execution,
                "verdict": pair.verdict.value,
                "correspondences": [
                    {
                        "source": {
                            "kind": item.source.kind.value,
                            "namespace": item.source.namespace,
                            "identifier": item.source.identifier,
                        },
                        "target": {
                            "kind": item.target.kind.value,
                            "namespace": item.target.namespace,
                            "identifier": item.target.identifier,
                        },
                        "verdict": item.verdict.value,
                        "source_transition": (
                            None
                            if item.source_transition is None
                            else {
                                "before": serialize_value(item.source_transition.before),
                                "after": serialize_value(item.source_transition.after),
                            }
                        ),
                        "target_transition": (
                            None
                            if item.target_transition is None
                            else {
                                "before": serialize_value(item.target_transition.before),
                                "after": serialize_value(item.target_transition.after),
                            }
                        ),
                    }
                    for item in pair.correspondences
                ],
                "expression_correspondences": [
                    {
                        "source": _expression_to_data(item.source),
                        "target": _expression_to_data(item.target),
                        "verdict": item.verdict.value,
                        "source_transition": _transition_to_data(item.source_transition),
                        "target_transition": _transition_to_data(item.target_transition),
                        "source_components": _components_to_data(item.source_components),
                        "target_components": _components_to_data(item.target_components),
                    }
                    for item in pair.expression_correspondences
                ],
            }
            for pair in result.pairs
        ],
        "evidence_graph": evidence_graph_to_data(build_validation_evidence_graph(contract, result)),
    }

    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    return output_path


def _entity_to_data(entity: EntityRef) -> dict[str, str]:
    return {
        "kind": entity.kind.value,
        "namespace": entity.namespace,
        "identifier": entity.identifier,
    }


def _load_entity(data: dict[str, object]) -> EntityRef:
    return EntityRef(
        kind=EntityKind(str(data["kind"])),
        namespace=str(data["namespace"]),
        identifier=str(data["identifier"]),
    )


def _candidate_set_to_data(
    candidate_set: CandidateSet,
    correspondences: list[CorrespondenceCandidate],
    expression_correspondences: list[ExpressionCorrespondenceCandidate],
) -> dict[str, object]:
    ranked_data: list[dict[str, object]] = []
    for ranked in candidate_set.candidates:
        if ranked.shape == CandidateShape.FIELD:
            if not isinstance(ranked.candidate, CorrespondenceCandidate):
                raise ValueError("Field ranking must reference a field correspondence.")
            if ranked.candidate not in correspondences:
                raise ValueError("Ranked field correspondence is missing from the contract.")
            reference = correspondence_id(ranked.candidate)
            target: object = _entity_to_data(ranked.candidate.target)
        else:
            if not isinstance(ranked.candidate, ExpressionCorrespondenceCandidate):
                raise ValueError("Expression ranking must reference an expression correspondence.")
            if ranked.candidate not in expression_correspondences:
                raise ValueError("Ranked expression correspondence is missing from the contract.")
            reference = expression_correspondence_id(ranked.candidate)
            target = _expression_to_data(ranked.candidate.target)
        ranked_data.append(
            {
                "shape": ranked.shape.value,
                "correspondence": reference,
                "rank": ranked.rank,
                "score": ranked.score,
                "factors": ranked.factors,
                "target": target,
            }
        )

    return {
        "source": _entity_to_data(candidate_set.source),
        "status": candidate_set.status.value,
        "candidates": ranked_data,
    }


def _expression_to_data(expression: EntityExpression) -> dict[str, object]:
    return {
        "kind": expression.kind.value,
        "components": [_entity_to_data(component) for component in expression.components],
    }


def _load_expression(data: dict[str, object]) -> EntityExpression:
    raw_components = data["components"]
    if not isinstance(raw_components, list):
        raise ValueError("Expression components must be a list.")

    components: list[EntityRef] = []
    for raw_component in raw_components:
        if not isinstance(raw_component, dict):
            raise ValueError("Expression component must be an object.")
        components.append(
            EntityRef(
                kind=EntityKind(str(raw_component["kind"])),
                namespace=str(raw_component["namespace"]),
                identifier=str(raw_component["identifier"]),
            )
        )

    return EntityExpression(
        kind=ExpressionKind(str(data["kind"])),
        components=tuple(components),
    )


def _transition_to_data(transition: ObservedTransition | None) -> object:
    if transition is None:
        return None
    return {
        "before": serialize_value(transition.before),
        "after": serialize_value(transition.after),
    }


def _components_to_data(
    components: list[ExpressionComponentValidation],
) -> list[dict[str, object]]:
    return [
        {
            "entity": _entity_to_data(component.entity),
            "transition": _transition_to_data(component.transition),
        }
        for component in components
    ]
