from pathlib import Path

from invariant_cli.analysis.service import analyze_program
from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.model import (
    CorrespondenceCandidate,
    FunctionCorrespondenceStatus,
    Relation,
    RelationKind,
)
from invariant_cli.matching.model import EntityKind, EntityRef


def test_function_candidates_are_anchored_by_mapped_state(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text(
        'state = {}\n\ndef pay(amount):\n    state["balance"] -= amount\n',
        encoding="utf-8",
    )
    target = tmp_path / "target.py"
    target.write_text(
        'account = {}\n\ndef process(value):\n    account["remaining"] -= value\n\n'
        "def unrelated(value):\n    return value * 2\n",
        encoding="utf-8",
    )
    correspondence = CorrespondenceCandidate(
        source=EntityRef(EntityKind.JSON_FIELD, "source.json", "balance"),
        target=EntityRef(EntityKind.JSON_FIELD, "target.json", "remaining"),
        relation=Relation(RelationKind.EXACT),
        evidence=[],
    )

    candidates = infer_function_correspondences(
        analyze_program(source), analyze_program(target), [correspondence]
    )

    assert [(item.source.identifier, item.target.identifier) for item in candidates] == [
        ("pay", "process")
    ]
    assert candidates[0].status == FunctionCorrespondenceStatus.CANDIDATE
