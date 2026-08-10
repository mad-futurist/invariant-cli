import json
from pathlib import Path
from uuid import uuid4

import yaml

from invariant_cli.contracts.model import (
    CandidateTranslationContract,
    CorrespondenceCandidate,
    DynamicEvidence,
    ExecutionPairRef,
    ObservationSelector,
    Relation,
    RelationKind,
)
from invariant_cli.contracts.validation import ContractValidationResult
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
                    "resource": candidate.source.resource,
                    "path": candidate.source.path,
                },
                "target": {
                    "resource": candidate.target.resource,
                    "path": candidate.target.path,
                },
                "relation": {
                    "kind": candidate.relation.kind.value,
                    "scale": candidate.relation.scale,
                    "offset": candidate.relation.offset,
                },
                "evidence": {
                    "dynamic": {
                        "matched_pairs": (candidate.evidence.matched_pairs),
                        "total_pairs": (candidate.evidence.total_pairs),
                        "distinct_transitions": (candidate.evidence.distinct_transitions),
                        "score": candidate.evidence.score,
                    }
                },
            }
            for candidate in contract.correspondences
        ],
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
        dynamic = entry["evidence"]["dynamic"]

        correspondences.append(
            CorrespondenceCandidate(
                source=ObservationSelector(
                    resource=entry["source"]["resource"],
                    path=entry["source"]["path"],
                ),
                target=ObservationSelector(
                    resource=entry["target"]["resource"],
                    path=entry["target"]["path"],
                ),
                relation=Relation(
                    kind=RelationKind(entry.get("relation", {}).get("kind", "exact")),
                    scale=str(entry.get("relation", {}).get("scale", "1")),
                    offset=str(entry.get("relation", {}).get("offset", "0")),
                ),
                evidence=DynamicEvidence(
                    matched_pairs=dynamic["matched_pairs"],
                    total_pairs=dynamic["total_pairs"],
                    distinct_transitions=dynamic["distinct_transitions"],
                ),
            )
        )

    return CandidateTranslationContract(
        version=data["version"],
        paired_executions=paired_executions,
        correspondences=correspondences,
    )


def save_contract_validation(
    result: ContractValidationResult,
    *,
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
                            "resource": item.source.resource,
                            "path": item.source.path,
                        },
                        "target": {
                            "resource": item.target.resource,
                            "path": item.target.path,
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
            }
            for pair in result.pairs
        ],
    }

    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    return output_path
