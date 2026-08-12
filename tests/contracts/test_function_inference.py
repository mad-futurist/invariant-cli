from pathlib import Path

from invariant_cli.analysis.service import analyze_program
from invariant_cli.contracts.function_inference import (
    FunctionCompatibilityPolicy,
    infer_function_correspondences,
)
from invariant_cli.contracts.model import (
    CandidateSet,
    CandidateSetStatus,
    CandidateShape,
    CorrespondenceCandidate,
    FunctionCorrespondenceStatus,
    RankedCandidate,
    Relation,
    RelationKind,
)
from invariant_cli.matching.model import EntityKind, EntityRef, LogicalStateIdentity


def _candidate_set(
    *candidates: CorrespondenceCandidate,
    status: CandidateSetStatus = CandidateSetStatus.WELL_SUPPORTED_CANDIDATE,
) -> CandidateSet:
    return CandidateSet(
        source=candidates[0].source,
        status=status,
        candidates=[
            RankedCandidate(CandidateShape.FIELD, 1, 100, {}, candidate) for candidate in candidates
        ],
    )


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
        source=EntityRef(EntityKind.JSON_FIELD, "state.json", "balance"),
        target=EntityRef(EntityKind.JSON_FIELD, "account.json", "remaining"),
        relation=Relation(RelationKind.EXACT),
        evidence=[],
    )

    candidate_set = _candidate_set(correspondence)
    candidates = infer_function_correspondences(
        analyze_program(source), analyze_program(target), [candidate_set]
    )

    assert [(item.source.identifier, item.target.identifier) for item in candidates] == [
        ("pay", "process")
    ]
    assert candidates[0].status == FunctionCorrespondenceStatus.CANDIDATE


def test_ambiguous_state_mapping_makes_function_candidates_inconclusive(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text('def pay(value):\n    state["balance"] -= value\n', encoding="utf-8")
    target = tmp_path / "target.py"
    target.write_text(
        'def process(value):\n    account["remaining"] -= value\n    account["total"] -= value\n',
        encoding="utf-8",
    )
    source_state = EntityRef(EntityKind.JSON_FIELD, "state.json", "balance")
    alternatives = [
        CorrespondenceCandidate(
            source_state,
            EntityRef(EntityKind.JSON_FIELD, "account.json", target_name),
            Relation(RelationKind.EXACT),
            [],
        )
        for target_name in ("remaining", "total")
    ]

    candidates = infer_function_correspondences(
        analyze_program(source),
        analyze_program(target),
        [_candidate_set(*alternatives, status=CandidateSetStatus.AMBIGUOUS)],
    )

    assert candidates
    assert {item.status for item in candidates} == {FunctionCorrespondenceStatus.INCONCLUSIVE}
    assert all(
        item.evidence[0].attributes["reason"] == "ambiguous_state_mapping" for item in candidates
    )


def test_logical_owner_prevents_same_identifier_from_overwriting_mapping(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text('def pay(value):\n    account["balance"] -= value\n', encoding="utf-8")
    target = tmp_path / "target.py"
    target.write_text('def process(value):\n    ledger["remaining"] -= value\n', encoding="utf-8")
    account = CorrespondenceCandidate(
        EntityRef(EntityKind.JSON_FIELD, "account.json", "balance"),
        EntityRef(EntityKind.JSON_FIELD, "ledger.json", "remaining"),
        Relation(RelationKind.EXACT),
        [],
    )
    invoice = CorrespondenceCandidate(
        EntityRef(EntityKind.JSON_FIELD, "invoice.json", "balance"),
        EntityRef(EntityKind.JSON_FIELD, "archive.json", "remaining"),
        Relation(RelationKind.EXACT),
        [],
    )

    candidates = infer_function_correspondences(
        analyze_program(source),
        analyze_program(target),
        [_candidate_set(account), _candidate_set(invoice)],
    )

    assert len(candidates) == 1
    assert candidates[0].status == FunctionCorrespondenceStatus.CANDIDATE
    assert candidates[0].mapped_state_writes == ((account.source, account.target),)


def test_extra_state_write_is_forbidden_unless_policy_allows_effect(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text('def pay(value):\n    state["balance"] -= value\n', encoding="utf-8")
    target = tmp_path / "target.py"
    target.write_text(
        'def process(value):\n    account["remaining"] -= value\n'
        '    audit["last_payment"] = value\n',
        encoding="utf-8",
    )
    mapping = CorrespondenceCandidate(
        EntityRef(EntityKind.JSON_FIELD, "state.json", "balance"),
        EntityRef(EntityKind.JSON_FIELD, "account.json", "remaining"),
        Relation(RelationKind.EXACT),
        [],
    )
    programs = (analyze_program(source), analyze_program(target), [_candidate_set(mapping)])

    rejected = infer_function_correspondences(*programs)
    allowed = infer_function_correspondences(
        *programs,
        policy=FunctionCompatibilityPolicy(
            frozenset({("state_write", LogicalStateIdentity("audit", "last_payment"))})
        ),
    )

    assert rejected[0].status == FunctionCorrespondenceStatus.REJECTED
    assert rejected[0].evidence[0].attributes["forbidden_extra_effects"] == [
        {"kind": "state_write", "target": "audit.last_payment"}
    ]
    assert allowed[0].status == FunctionCorrespondenceStatus.CANDIDATE
