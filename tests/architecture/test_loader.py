from pathlib import Path

import pytest

from invariant_cli.architecture.loader import load_architecture
from invariant_cli.architecture.model import ObligationKind


def test_load_architecture_v1(tmp_path: Path) -> None:
    path = tmp_path / "invariant.arch.yaml"
    path.write_text(
        """version: 1
components:
  - id: service
    modules: [payment]
  - id: persistence
    modules: [repository]
rules:
  - id: dependency
    kind: require_dependency
    from: service
    to: persistence
""",
        encoding="utf-8",
    )

    model = load_architecture(path)

    assert model.version == 1
    assert model.obligations[0].kind == ObligationKind.REQUIRE_DEPENDENCY


def test_architecture_rejects_unknown_component(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        """version: 1
components: []
rules:
  - id: invalid
    kind: forbid_state_write
    component: missing
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown components"):
        load_architecture(path)


def test_state_owner_requires_logical_owner_and_full_path(tmp_path: Path) -> None:
    path = tmp_path / "invalid-state.yaml"
    path.write_text(
        """version: 1
components:
  - id: persistence
    modules: [repository]
rules:
  - id: owner
    kind: state_write_owner
    component: persistence
    state: [remaining_eur]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="logical owner and path"):
        load_architecture(path)
