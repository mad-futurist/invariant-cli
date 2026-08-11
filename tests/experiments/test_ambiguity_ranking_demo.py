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
EXPERIMENT = REPOSITORY_ROOT / "experiments" / "ambiguity_ranking_demo"


def _reset(demo: Path, balance: int) -> None:
    subprocess.run(
        [sys.executable, str(demo / "reset.py"), str(balance)],
        cwd=demo,
        check=True,
    )


def _capture(demo: Path, app_path: str, payment: int) -> str:
    executions = demo / ".invariant" / "executions"
    before = set(executions.glob("*.json"))
    result = runner.invoke(
        app,
        ["capture", "--", sys.executable, app_path, str(payment)],
    )
    assert result.exit_code == 0, result.stdout
    created = set(executions.glob("*.json")) - before
    assert len(created) == 1
    return created.pop().stem


def test_ambiguity_is_explicit_and_alternatives_survive_validation(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    demo = tmp_path / "ambiguity_ranking_demo"
    shutil.copytree(EXPERIMENT, demo)
    monkeypatch.chdir(demo)
    assert runner.invoke(app, ["init", "--name", "ambiguity-ranking-demo"]).exit_code == 0

    pairs: list[tuple[str, str]] = []
    for balance, payment in [(100, 30), (100, 60), (250, 60)]:
        _reset(demo, balance)
        pairs.append(
            (
                _capture(demo, "source/app.py", payment),
                _capture(demo, "target/app.py", payment),
            )
        )

    infer_args = ["contract", "infer"]
    for source_id, target_id in pairs:
        infer_args.extend(["--pair", f"{source_id}:{target_id}"])
    inference = runner.invoke(app, infer_args)
    assert inference.exit_code == 0, inference.stdout
    assert "Candidate correspondences: 2" in inference.stdout
    assert "state.json#balance: ambiguous" in inference.stdout

    contract_file = next((demo / ".invariant" / "contracts").glob("*.candidate.yaml"))
    contract = yaml.safe_load(contract_file.read_text(encoding="utf-8"))
    candidate_set = contract["candidate_sets"][0]
    assert candidate_set["status"] == "ambiguous"
    assert [candidate["rank"] for candidate in candidate_set["candidates"]] == [1, 1, 2]
    direct_candidates = [
        candidate for candidate in candidate_set["candidates"] if candidate["shape"] == "field"
    ]
    assert {candidate["target"]["identifier"] for candidate in direct_candidates} == {
        "remaining",
        "total",
    }
    contains = [edge for edge in contract["evidence_graph"]["edges"] if edge["kind"] == "contains"]
    assert len(contains) == 3

    _reset(demo, 300)
    source_id = _capture(demo, "source/app.py", 75)
    target_id = _capture(demo, "target/app.py", 75)
    validation = runner.invoke(
        app,
        ["contract", "validate", str(contract_file), "--pair", f"{source_id}:{target_id}"],
    )
    assert validation.exit_code == 0, validation.stdout
    assert "Contract validation: PASS" in validation.stdout

    result_file = next((demo / ".invariant" / "results").glob("*.contract-validation.json"))
    result = json.loads(result_file.read_text(encoding="utf-8"))
    assert len(result["pairs"][0]["correspondences"]) == 2
    assert len(result["pairs"][0]["expression_correspondences"]) == 1
