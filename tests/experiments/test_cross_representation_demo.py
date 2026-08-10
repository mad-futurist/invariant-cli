import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from pytest import MonkeyPatch
from typer.testing import CliRunner

from invariant_cli.cli import app

runner = CliRunner()

REPOSITORY_ROOT = Path(__file__).parents[2]
EXPERIMENT = REPOSITORY_ROOT / "experiments" / "cross_representation_demo"


def _reset(demo: Path, balance_cents: int) -> None:
    subprocess.run(
        [sys.executable, str(demo / "reset.py"), str(balance_cents)],
        cwd=demo,
        check=True,
    )


def _capture(demo: Path, scope: str, app_path: str, amount: str) -> str:
    executions = demo / ".invariant" / "executions"
    before = set(executions.glob("*.json"))
    result = runner.invoke(
        app,
        [
            "capture",
            "--observe",
            scope,
            "--",
            sys.executable,
            app_path,
            amount,
        ],
    )

    assert result.exit_code == 0, result.stdout
    created = set(executions.glob("*.json")) - before
    assert len(created) == 1
    return created.pop().stem


def test_cross_representation_evidence_graph_end_to_end(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    demo = tmp_path / "cross_representation_demo"
    shutil.copytree(EXPERIMENT, demo)
    monkeypatch.chdir(demo)

    assert runner.invoke(app, ["init", "--name", "cross-representation-demo"]).exit_code == 0

    pairs: list[tuple[str, str]] = []
    for balance_cents, payment_cents in [(10000, 3000), (10000, 6000), (25000, 6000)]:
        _reset(demo, balance_cents)
        source_id = _capture(demo, "source/*.db", "source/app.py", str(payment_cents))
        target_id = _capture(
            demo,
            "target/*.json",
            "target/app.py",
            f"{payment_cents / 100:g}",
        )
        pairs.append((source_id, target_id))

    infer_args = ["contract", "infer"]
    for source_id, target_id in pairs:
        infer_args.extend(["--pair", f"{source_id}:{target_id}"])

    infer_result = runner.invoke(app, infer_args)
    assert infer_result.exit_code == 0, infer_result.stdout
    assert "Candidate correspondences: 1" in infer_result.stdout

    contract_file = next((demo / ".invariant" / "contracts").glob("*.candidate.yaml"))
    contract_data = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
    correspondence = contract_data["correspondences"][0]
    assert correspondence["source"] == {
        "kind": "sqlite_field",
        "namespace": "source/legacy.db",
        "identifier": "wallets[id=1].balance_cents",
    }
    assert correspondence["target"] == {
        "kind": "json_field",
        "namespace": "target/account.json",
        "identifier": "remaining_eur",
    }
    assert correspondence["relation"] == {
        "kind": "affine",
        "scale": "0.01",
        "offset": "0",
    }

    candidate_graph = contract_data["evidence_graph"]
    assert candidate_graph["version"] == 2
    assert {node["kind"] for node in candidate_graph["nodes"]} == {
        "entity",
        "correspondence",
        "relation",
        "evidence",
        "execution_pair",
    }
    assert {edge["kind"] for edge in candidate_graph["edges"]} == {
        "has_source",
        "has_target",
        "uses_relation",
        "supports",
        "derived_from",
    }

    _reset(demo, 30000)
    source_id = _capture(demo, "source/*.db", "source/app.py", "7500")
    target_id = _capture(demo, "target/*.json", "target/app.py", "75")
    validation_result = runner.invoke(
        app,
        ["contract", "validate", str(contract_file), "--pair", f"{source_id}:{target_id}"],
    )
    assert validation_result.exit_code == 0, validation_result.stdout
    assert "Contract validation: PASS" in validation_result.stdout

    result_file = next((demo / ".invariant" / "results").glob("*.contract-validation.json"))
    result_data = json.loads(result_file.read_text(encoding="utf-8"))
    validation_graph = result_data["evidence_graph"]
    validation_nodes = [node for node in validation_graph["nodes"] if node["kind"] == "validation"]
    assert len(validation_nodes) == 1
    assert validation_nodes[0]["attributes"]["verdict"] == "PASS"
    assert "validates" in {edge["kind"] for edge in validation_graph["edges"]}
