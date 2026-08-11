from dataclasses import replace
from typing import cast

from invariant_cli.contracts.enrichment import enrich_with_static_usage
from invariant_cli.contracts.inference import infer_correspondences
from invariant_cli.contracts.model import CandidateSetStatus, CorrespondenceCandidate
from invariant_cli.contracts.ranking import build_candidate_sets
from invariant_cli.matching.model import Evidence, EvidenceEffect, EvidenceKind
from invariant_cli.matching.static.model import FieldUsage, UsageOperation
from invariant_cli.observation.model import Observation, ValueChange


def _pairs() -> list[tuple[list[Observation], list[Observation]]]:
    pairs = []
    for before, after in [(100, 70), (100, 40), (250, 190)]:
        pairs.append(
            (
                [Observation("state.json", "json", [ValueChange("balance", before, after)])],
                [
                    Observation(
                        "account.json",
                        "json",
                        [
                            ValueChange("remaining", before, after),
                            ValueChange("total", before, after),
                        ],
                    )
                ],
            )
        )
    return pairs


def test_marks_equal_candidates_ambiguous_and_preserves_both() -> None:
    candidates = infer_correspondences(_pairs())
    candidate_sets = build_candidate_sets(candidates, [])

    assert len(candidate_sets) == 1
    candidate_set = candidate_sets[0]
    assert candidate_set.status == CandidateSetStatus.AMBIGUOUS
    assert [candidate.rank for candidate in candidate_set.candidates] == [1, 1]
    assert {
        cast(CorrespondenceCandidate, candidate.candidate).target.identifier
        for candidate in candidate_set.candidates
    } == {"remaining", "total"}


def test_static_evidence_deterministically_ranks_without_dropping_alternative() -> None:
    candidates = enrich_with_static_usage(
        infer_correspondences(_pairs()),
        {
            "balance": FieldUsage(
                "balance",
                {UsageOperation.READ, UsageOperation.WRITE, UsageOperation.SUBTRACT},
            )
        },
        {
            "remaining": FieldUsage(
                "remaining",
                {UsageOperation.READ, UsageOperation.WRITE, UsageOperation.SUBTRACT},
            ),
            "total": FieldUsage("total", {UsageOperation.READ}),
        },
    )

    candidate_set = build_candidate_sets(candidates, [])[0]
    assert candidate_set.status == CandidateSetStatus.CONFIDENT_CANDIDATE
    assert len(candidate_set.candidates) == 2
    first = cast(CorrespondenceCandidate, candidate_set.candidates[0].candidate)
    second = cast(CorrespondenceCandidate, candidate_set.candidates[1].candidate)
    assert first.target.identifier == "remaining"
    assert candidate_set.candidates[0].rank == 1
    assert second.target.identifier == "total"
    assert candidate_set.candidates[1].rank == 2


def test_marks_dynamic_only_candidate_as_insufficient_evidence() -> None:
    candidate = infer_correspondences(_pairs())[0]
    dynamic_only = replace(candidate, evidence=[candidate.evidence[0]])

    candidate_set = build_candidate_sets([dynamic_only], [])[0]

    assert candidate_set.status == CandidateSetStatus.INSUFFICIENT_EVIDENCE


def test_marks_source_without_surviving_hypotheses_rejected() -> None:
    source = infer_correspondences(_pairs())[0].source
    candidate_set = build_candidate_sets([], [], sources=[source])[0]

    assert candidate_set.status == CandidateSetStatus.REJECTED
    assert candidate_set.candidates == []


def test_contradicting_evidence_rejects_candidate_without_dropping_it() -> None:
    candidate = infer_correspondences(_pairs())[0]
    contradicted = replace(
        candidate,
        evidence=[
            *candidate.evidence,
            Evidence(
                kind=EvidenceKind.STATIC_DATA_FLOW,
                producer="python-dataflow-v1",
                effect=EvidenceEffect.CONTRADICTS,
            ),
        ],
    )

    candidate_set = build_candidate_sets([contradicted], [])[0]

    assert candidate_set.status == CandidateSetStatus.REJECTED
    assert [ranked.candidate for ranked in candidate_set.candidates] == [contradicted]
