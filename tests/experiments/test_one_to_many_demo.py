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
EXPERIMENT = REPOSITORY_ROOT / "experiments" / "one_to_many_demo"


def _reset(demo: Path, balance_cents: int, principal_eur: int, reserve_eur: int) -> None:
    subprocess.run(
        [
            sys.executable,
            str(demo / "reset.py"),
            str(balance_cents),
            str(principal_eur),
            str(reserve_eur),
        ],
        cwd=demo,
        check=True,
    )


def _capture(demo: Path, scope: str, command: list[str]) -> str:
    executions = demo / ".invariant" / "executions"
    before = set(executions.glob("*.json"))
    result = runner.invoke(app, ["capture", "--observe", scope, "--", *command])
    assert result.exit_code == 0, result.stdout
    created = set(executions.glob("*.json")) - before
    assert len(created) == 1
    return created.pop().stem


def test_one_to_many_demo_end_to_end(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    demo = tmp_path / "one_to_many_demo"
    shutil.copytree(EXPERIMENT, demo)
    monkeypatch.chdir(demo)
    assert runner.invoke(app, ["init", "--name", "one-to-many-demo"]).exit_code == 0

    runs = [
        (10000, 80, 20, 3000, 25, 5),
        (10000, 70, 30, 6000, 50, 10),
        (25000, 100, 150, 6000, 30, 30),
    ]
    pairs: list[tuple[str, str]] = []
    for balance, principal, reserve, payment, principal_payment, reserve_payment in runs:
        _reset(demo, balance, principal, reserve)
        source_id = _capture(
            demo,
            "source/*.db",
            [sys.executable, "source/app.py", str(payment)],
        )
        target_id = _capture(
            demo,
            "target/*.json",
            [
                sys.executable,
                "target/app.py",
                str(principal_payment),
                str(reserve_payment),
            ],
        )
        pairs.append((source_id, target_id))

    infer_args = ["contract", "infer"]
    for source_id, target_id in pairs:
        infer_args.extend(["--pair", f"{source_id}:{target_id}"])
    infer_result = runner.invoke(app, infer_args)
    assert infer_result.exit_code == 0, infer_result.stdout
    assert "Candidate correspondences: 0" in infer_result.stdout
    assert "Expression correspondences: 1" in infer_result.stdout

    contract_file = next((demo / ".invariant" / "contracts").glob("*.candidate.yaml"))
    contract_data = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
    assert contract_data["version"] == 3
    assert contract_data["correspondences"] == []
    expression = contract_data["expression_correspondences"][0]
    assert expression["source"]["kind"] == "identity"
    assert expression["source"]["components"][0]["identifier"] == ("wallets[id=1].balance_cents")
    assert expression["target"]["kind"] == "sum"
    assert [component["identifier"] for component in expression["target"]["components"]] == [
        "principal_eur",
        "reserve_eur",
    ]
    assert expression["relation"] == {"kind": "affine", "scale": "0.01", "offset": "0"}

    graph = contract_data["evidence_graph"]
    assert graph["version"] == 2
    assert len([node for node in graph["nodes"] if node["kind"] == "expression"]) == 2
    assert len([edge for edge in graph["edges"] if edge["kind"] == "has_component"]) == 3

    _reset(demo, 30000, 110, 190)
    source_id = _capture(
        demo,
        "source/*.db",
        [sys.executable, "source/app.py", "7500"],
    )
    target_id = _capture(
        demo,
        "target/*.json",
        [sys.executable, "target/app.py", "20", "55"],
    )
    validation = runner.invoke(
        app,
        ["contract", "validate", str(contract_file), "--pair", f"{source_id}:{target_id}"],
    )
    assert validation.exit_code == 0, validation.stdout
    assert "Contract validation: PASS" in validation.stdout

    result_file = next((demo / ".invariant" / "results").glob("*.contract-validation.json"))
    result = json.loads(result_file.read_text(encoding="utf-8"))
    expression_result = result["pairs"][0]["expression_correspondences"][0]
    assert expression_result["verdict"] == "PASS"
    assert expression_result["target_transition"] == {"before": 300, "after": 225}
    assert len(expression_result["target_components"]) == 2
    assert "validates" in {edge["kind"] for edge in result["evidence_graph"]["edges"]}
