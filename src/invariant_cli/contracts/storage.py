from pathlib import Path
from uuid import uuid4

import yaml

from invariant_cli.contracts.model import CandidateTranslationContract


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
