from __future__ import annotations

import os
from pathlib import Path

import pytest
from experiments.spec_kitty_preflight_pilot.harness import (
    load_manifest,
    load_scenario,
    run_scenario,
)
from experiments.spec_kitty_preflight_pilot.run_scenario import DEFAULT_COMMAND


@pytest.mark.external_corpus
@pytest.mark.parametrize(
    ("candidate", "scenario", "verdict", "expected", "observed", "missing"),
    [
        ("bad", "multiple_dirty", "FAIL", ["WP01", "WP03"], ["WP01"], ["WP03"]),
        (
            "fixed",
            "multiple_dirty",
            "PASS",
            ["WP01", "WP03"],
            ["WP01", "WP03"],
            [],
        ),
        ("bad", "missing_worktree", "FAIL", ["WP03"], [], ["WP03"]),
        ("fixed", "missing_worktree", "PASS", ["WP03"], ["WP03"], []),
    ],
)
def test_historical_candidate_verdicts(
    candidate: str,
    scenario: str,
    verdict: str,
    expected: list[str],
    observed: list[str],
    missing: list[str],
) -> None:
    configured = os.environ.get("INVARIANT_SPEC_KITTY_CORPUS")
    if configured is None:
        pytest.skip("Set INVARIANT_SPEC_KITTY_CORPUS to run the historical corpus.")
    corpus_root = Path(configured)
    if not corpus_root.is_dir():
        pytest.fail(f"Configured corpus does not exist: {corpus_root}")

    record = run_scenario(
        corpus_root,
        load_manifest(),
        candidate,
        load_scenario(scenario),
        DEFAULT_COMMAND,
    )

    verification = record["verification"]
    assert isinstance(verification, dict)
    assert verification["verdict"] == verdict
    evidence = verification["results"][0]["evidence"][0]
    assert evidence["expected"] == expected
    assert evidence["observed"] == observed
    assert evidence["missing"] == missing
    assert record["git_before"] == record["git_after"]
