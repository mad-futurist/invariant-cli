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
EXPERIMENT = REPOSITORY_ROOT / "experiments" / "static_usage_demo"


def _reset(demo: Path, balance_cents: int) -> None:
    subprocess.run(
        [sys.executable, str(demo / "reset.py"), str(balance_cents)],
        cwd=demo,
        check=True,
    )


def _capture(demo: Path, app_path: str, amount: str) -> str:
    executions = demo / ".invariant" / "executions"
    before = set(executions.glob("*.json"))

    result = runner.invoke(
        app,
        [
            "capture",
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


def test_static_usage_demo_end_to_end(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    demo = tmp_path / "static_usage_demo"
    shutil.copytree(EXPERIMENT, demo)
    monkeypatch.chdir(demo)

    init_result = runner.invoke(app, ["init", "--name", "static-usage-demo"])
    assert init_result.exit_code == 0

    training_runs = [
        (10000, 3000),
        (10000, 6000),
        (25000, 6000),
    ]
    pairs: list[tuple[str, str]] = []

    for balance_cents, payment_cents in training_runs:
        _reset(demo, balance_cents)
        source_id = _capture(demo, "source/app.py", str(payment_cents))
        target_id = _capture(demo, "target/app.py", f"{payment_cents / 100:g}")
        pairs.append((source_id, target_id))

    infer_args = ["contract", "infer"]
    for source_id, target_id in pairs:
        infer_args.extend(["--pair", f"{source_id}:{target_id}"])
    infer_args.extend(
        [
            "--source-code",
            str(demo / "source" / "app.py"),
            "--target-code",
            str(demo / "target" / "app.py"),
        ]
    )

    infer_result = runner.invoke(app, infer_args)
    assert infer_result.exit_code == 0, infer_result.stdout
    assert "Candidate correspondences: 1" in infer_result.stdout
    assert "static evidence: read, subtract, write" in infer_result.stdout

    contract_files = list((demo / ".invariant" / "contracts").glob("*.candidate.yaml"))
    assert len(contract_files) == 1

    contract_data = yaml.safe_load(contract_files[0].read_text(encoding="utf-8"))
    correspondence = contract_data["correspondences"][0]
    assert correspondence["relation"] == {
        "kind": "affine",
        "scale": "0.01",
        "offset": "0",
    }
    static_evidence = next(
        item for item in correspondence["evidence"] if item["kind"] == "static_usage"
    )
    assert static_evidence == {
        "kind": "static_usage",
        "producer": "python-ast-v1",
        "family": "static_program",
        "effect": "supports",
        "attributes": {
            "source_operations": ["read", "subtract", "write"],
            "target_operations": ["read", "subtract", "write"],
            "common_operations": ["read", "subtract", "write"],
        },
    }

    _reset(demo, 30000)
    held_out_source = _capture(demo, "source/app.py", "7500")
    held_out_target = _capture(demo, "target/app.py", "75")

    validation_result = runner.invoke(
        app,
        [
            "contract",
            "validate",
            str(contract_files[0]),
            "--pair",
            f"{held_out_source}:{held_out_target}",
        ],
    )

    assert validation_result.exit_code == 0, validation_result.stdout
    assert "Contract validation: PASS" in validation_result.stdout

    result_files = list((demo / ".invariant" / "results").glob("*.contract-validation.json"))
    assert len(result_files) == 1
    result_data = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result_data["verdict"] == "PASS"
