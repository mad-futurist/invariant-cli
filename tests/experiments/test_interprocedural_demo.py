import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pytest import MonkeyPatch
from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()
REPOSITORY_ROOT = Path(__file__).parents[2]
EXPERIMENT = REPOSITORY_ROOT / "experiments" / "interprocedural_demo"


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
    ("target", "effect", "status"),
    [
        ("target", "supports", "confident_candidate"),
        ("target_negative", "contradicts", "rejected"),
        ("target_unresolved", "neutral", "confident_candidate"),
    ],
)
def test_interprocedural_program_context(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    target: str,
    effect: str,
    status: str,
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
                _capture(demo, "source/service.py", str(payment_cents)),
                _capture(demo, f"{target}/payment.py", f"{payment_cents / 100:g}"),
            )
        )

    args = ["contract", "infer"]
    for source_id, target_id in pairs:
        args.extend(["--pair", f"{source_id}:{target_id}"])
    args.extend(
        [
            "--source-code",
            str(demo / "source"),
            "--target-code",
            str(demo / target),
        ]
    )
    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stdout
    assert f"call-context evidence: {effect}" in result.stdout

    contract_path = next((demo / ".invariant" / "contracts").glob("*.candidate.yaml"))
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    candidate = next(
        item
        for item in contract["correspondences"]
        if item["source"]["identifier"] == "balance_cents"
        and item["target"]["identifier"] == "remaining_eur"
    )
    context = next(item for item in candidate["evidence"] if item["kind"] == "call_context")
    assert context["producer"] == "python-call-context-v1"
    assert context["effect"] == effect
    assert context["attributes"]["source_call_chain"] == ["pay", "persist_balance"]
    assert contract["candidate_sets"][0]["status"] == status

    evidence_node = next(
        node
        for node in contract["evidence_graph"]["nodes"]
        if node["kind"] == "evidence" and node["attributes"]["kind"] == "call_context"
    )
    assert evidence_node["attributes"]["effect"] == effect
    assert any(
        edge["source"] == evidence_node["id"] and edge["kind"] == effect
        for edge in contract["evidence_graph"]["edges"]
    )
