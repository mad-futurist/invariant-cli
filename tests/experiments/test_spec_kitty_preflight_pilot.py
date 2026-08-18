from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from experiments.spec_kitty_preflight_pilot.harness import (
    DIRTY_MARKER,
    load_manifest,
    load_scenario,
    reset_candidate,
    run_scenario,
    setup_candidate,
    stable_json,
)


def test_multiple_dirty_fixture_is_normalized_and_repeatable(tmp_path: Path) -> None:
    source, sha = _source_repository(tmp_path)
    manifest = load_manifest(_manifest(tmp_path, source, sha))
    corpus = tmp_path / "corpus"
    candidate = setup_candidate(corpus, manifest, "bad")
    scenario = load_scenario("multiple_dirty")
    command = [sys.executable, "-c", "print('controlled preflight')"]

    records = [run_scenario(corpus, manifest, "bad", scenario, command) for _ in range(3)]

    assert stable_json(records[0]) == stable_json(records[1]) == stable_json(records[2])
    assert records[0]["schema_version"] == 2
    specification = records[0]["specification"]
    assert isinstance(specification, dict)
    requirements = specification["requirements"]
    assert isinstance(requirements, tuple)
    assert [requirement["id"] for requirement in requirements] == [
        "FR-001",
        "FR-002",
        "FR-003",
        "FR-004",
    ]
    assert records[0]["execution"] == {
        "exit_code": 0,
        "stdout": "controlled preflight\n",
        "stderr": "",
    }
    before = records[0]["git_before"]
    assert isinstance(before, dict)
    statuses = before["worktree_status"]
    assert isinstance(statuses, dict)
    assert statuses["WP01"] == [f"?? {DIRTY_MARKER}"]
    assert statuses["WP02"] == []
    assert statuses["WP03"] == [f"?? {DIRTY_MARKER}"]
    assert statuses["WP04"] == []
    assert statuses["WP05"] == []
    assert statuses["WP06"] == []
    assert records[0]["git_before"] == records[0]["git_after"]
    assert candidate.name == "spec-kitty-bad"
    assert Path(_git(candidate, "remote", "get-url", "origin")).resolve() == candidate.resolve()
    assert _git(candidate, "rev-parse", "main") == sha
    assert _git(candidate, "rev-parse", "origin/main") == sha


def test_missing_worktree_is_recorded_and_reset_restores_it(tmp_path: Path) -> None:
    source, sha = _source_repository(tmp_path)
    manifest = load_manifest(_manifest(tmp_path, source, sha))
    corpus = tmp_path / "corpus"
    candidate = setup_candidate(corpus, manifest, "bad")

    record = run_scenario(
        corpus,
        manifest,
        "bad",
        load_scenario("missing_worktree"),
        [sys.executable, "-c", "raise SystemExit(7)"],
    )

    before = record["git_before"]
    assert isinstance(before, dict)
    statuses = before["worktree_status"]
    assert isinstance(statuses, dict)
    assert statuses["WP03"] is None
    assert record["execution"] == {"exit_code": 7, "stdout": "", "stderr": ""}
    reset_candidate(candidate, manifest, "bad")
    restored = candidate / ".worktrees" / f"{manifest.feature}-WP03"
    assert restored.is_dir()
    assert _git(restored, "status", "--porcelain") == ""


def test_manifest_pins_real_spec_kitty_artifacts() -> None:
    root = Path(__file__).parents[2] / "experiments" / "spec_kitty_preflight_pilot"
    raw = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert raw["candidates"]["bad"]["sha"] == ("0222ed3a837a6b3e1d73cd626fb0f8cf02e5e1a3")
    assert raw["candidates"]["fixed"]["sha"] == ("6985680ee5ef3b5f512cd2189d4fb8575420a571")
    assert {item["git_blob_sha1"] for item in raw["artifacts"]} == {
        "9df049e39581d23f44c87a5fe44e76eb8236cab3",
        "6deb05103d1b2c487f608750700f0343c6c6c097",
    }


def _source_repository(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    _run(["git", "init", "-b", "main"], source)
    _run(["git", "config", "user.email", "pilot@example.invalid"], source)
    _run(["git", "config", "user.name", "Invariant Pilot"], source)
    mission = source / "kitty-specs" / "017-preflight" / "tasks"
    mission.mkdir(parents=True)
    (mission.parent / "spec.md").write_text(
        """# Pilot spec

## Requirements

### Functional Requirements

**Pre-flight Validation**
- **FR-001**: Check all worktrees
- **FR-002**: Check target divergence
- **FR-003**: Aggregate all blockers
- **FR-004**: Fail without branch mutation
""",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02", "WP03", "WP04", "WP05", "WP06"):
        body = f"""---
work_package_id: "{wp_id}"
---

# Work Package Prompt: {wp_id}
"""
        if wp_id == "WP02":
            body += """
## Objectives & Success Criteria

**Functional Requirements Addressed**: FR-001, FR-002, FR-003, FR-004
"""
        (mission / f"{wp_id}.md").write_text(body, encoding="utf-8")
    _run(["git", "add", "."], source)
    _run(["git", "commit", "-m", "fixture"], source)
    return source, _git(source, "rev-parse", "HEAD")


def _manifest(tmp_path: Path, source: Path, sha: str) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "upstream": {"repository": str(source)},
                "mission": {
                    "feature": "017-preflight",
                    "work_package": "WP02",
                    "expected_work_packages": [
                        "WP01",
                        "WP02",
                        "WP03",
                        "WP04",
                        "WP05",
                        "WP06",
                    ],
                },
                "candidates": {
                    "bad": {"directory": "spec-kitty-bad", "sha": sha},
                    "fixed": {"directory": "spec-kitty-fixed", "sha": sha},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _git(cwd: Path, *args: str) -> str:
    return _run(["git", *args], cwd).stdout.strip()


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
