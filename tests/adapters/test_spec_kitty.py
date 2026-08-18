from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from invariant_cli.adapters.spec_kitty import SpecKittyAdapter, SpecKittyAdapterError
from invariant_cli.specifications.model import EpistemicStatus


def test_imports_selected_work_package_requirements_with_provenance(tmp_path: Path) -> None:
    _write_mission(tmp_path)
    adapter = SpecKittyAdapter()

    first = adapter.load(
        tmp_path,
        mission="017-preflight",
        work_package="WP02",
        requirement_ids=("FR-001", "FR-002", "FR-003", "FR-004"),
    )
    second = adapter.load(
        tmp_path,
        mission="017-preflight",
        work_package="WP02",
        requirement_ids=("FR-001", "FR-002", "FR-003", "FR-004"),
    )

    assert json.dumps(asdict(first), sort_keys=True) == json.dumps(asdict(second), sort_keys=True)
    assert [requirement.id for requirement in first.requirements] == [
        "FR-001",
        "FR-002",
        "FR-003",
        "FR-004",
    ]
    requirement = first.requirement("FR-003")
    assert requirement.text == "Display all pre-flight issues together"
    assert requirement.epistemic_status == EpistemicStatus.EXPLICIT
    assert [source.artifact for source in requirement.sources] == [
        "kitty-specs/017-preflight/spec.md",
        "kitty-specs/017-preflight/tasks/WP02-preflight-validation.md",
    ]
    assert requirement.sources[0].heading == (
        "Requirements > Functional Requirements > Pre-flight Validation"
    )
    assert requirement.sources[1].heading == "Objectives & Success Criteria"


def test_rejects_requirement_not_bound_to_work_package(tmp_path: Path) -> None:
    _write_mission(tmp_path)

    with pytest.raises(SpecKittyAdapterError, match="not assigned to WP02"):
        SpecKittyAdapter().load(
            tmp_path,
            mission="017-preflight",
            work_package="WP02",
            requirement_ids=("FR-005",),
        )


def _write_mission(repository_root: Path) -> None:
    mission = repository_root / "kitty-specs" / "017-preflight"
    tasks = mission / "tasks"
    tasks.mkdir(parents=True)
    (mission / "spec.md").write_text(
        """# Feature Specification

## Requirements

### Functional Requirements

#### Pre-flight Validation
- **FR-001**: Check all worktrees
- **FR-002**: Check target divergence
- **FR-003**: Display all pre-flight issues together
- **FR-004**: Exit without branch mutation

#### Conflict Forecast
- **FR-005**: Predict conflicts
""",
        encoding="utf-8",
    )
    (tasks / "WP02-preflight-validation.md").write_text(
        """---
work_package_id: "WP02"
---

# Work Package Prompt: WP02

## Objectives & Success Criteria

**Functional Requirements Addressed**: FR-001, FR-002, FR-003, FR-004
""",
        encoding="utf-8",
    )
