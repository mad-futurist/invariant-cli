import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pytest import MonkeyPatch
from typer.testing import CliRunner

from invariant_cli.cli import app
from invariant_cli.contracts.storage import load_candidate_contract
from invariant_cli.matching.model import EvidenceEffect, EvidenceKind

runner = CliRunner()
REPOSITORY_ROOT = Path(__file__).parents[2]
EXPERIMENT = REPOSITORY_ROOT / "experiments" / "dataflow_demo"


def _reset(demo: Path, balance_cents: int) -> None:
    subprocess.run(
        [sys.executable, str(demo / "reset.py"), str(balance_cents)],
        cwd=demo,
        check=True,
    )


def _capture(demo: Path, app_path: str, amount: str) -> str:
    executions = demo / ".invariant" / "executions"
    before = set(executions.glob("*.json"))
    result = runner.invoke(app, ["capture", "--", sys.executable, app_path, amount])
    assert result.exit_code == 0, result.stdout
    created = set(executions.glob("*.json")) - before
    assert len(created) == 1
    return created.pop().stem


@pytest.mark.parametrize(
    ("target", "effect", "status", "edge_kind"),
    [
        ("target_positive", "supports", "well_supported_candidate", "supports"),
        ("target_negative", "neutral", "well_supported_candidate", "neutral"),
    ],
)
def test_dataflow_demo_distinguishes_connected_and_accidental_candidates(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    target: str,
    effect: str,
    status: str,
    edge_kind: str,
) -> None:
    demo = tmp_path / target
    shutil.copytree(EXPERIMENT, demo)
    monkeypatch.chdir(demo)
    assert runner.invoke(app, ["init", "--name", target]).exit_code == 0

    pairs: list[tuple[str, str]] = []
    for balance_cents, payment_cents in [(10000, 3000), (10000, 6000), (25000, 6000)]:
        _reset(demo, balance_cents)
        pairs.append(
            (
                _capture(demo, "source/app.py", str(payment_cents)),
                _capture(demo, f"{target}/app.py", f"{payment_cents / 100:g}"),
            )
        )

    args = ["contract", "infer"]
    for source_id, target_id in pairs:
        args.extend(["--pair", f"{source_id}:{target_id}"])
    args.extend(
        [
            "--source-code",
            str(demo / "source" / "app.py"),
            "--target-code",
            str(demo / target / "app.py"),
        ]
    )
    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stdout
    assert f"data-flow evidence: {effect}" in result.stdout

    contract_path = next((demo / ".invariant" / "contracts").glob("*.candidate.yaml"))
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    candidate = next(
        item
        for item in contract["correspondences"]
        if item["source"]["identifier"] == "balance_cents"
        and item["target"]["identifier"] == "remaining_eur"
    )
    data_flow = next(item for item in candidate["evidence"] if item["kind"] == "static_data_flow")
    assert data_flow["producer"] == "python-dataflow-v1"
    assert data_flow["effect"] == effect
    assert data_flow["attributes"]["source"]["operations"] == ["subtract"]
    assert contract["candidate_sets"][0]["status"] == status

    loaded = load_candidate_contract(contract_path)
    loaded_data_flow = next(
        item
        for item in loaded.correspondences[0].evidence
        if item.kind == EvidenceKind.STATIC_DATA_FLOW
    )
    assert loaded_data_flow.effect == EvidenceEffect(effect)

    evidence_id = next(
        node["id"]
        for node in contract["evidence_graph"]["nodes"]
        if node["kind"] == "evidence" and node["attributes"]["kind"] == "static_data_flow"
    )
    assert any(
        edge["source"] == evidence_id and edge["kind"] == edge_kind
        for edge in contract["evidence_graph"]["edges"]
    )
