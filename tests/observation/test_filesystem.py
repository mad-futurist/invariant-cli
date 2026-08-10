from pathlib import Path

import pytest

from invariant_cli.observation.filesystem import diff_snapshots, snapshot_directory


def test_detects_modified_file(tmp_path: Path) -> None:
    file = tmp_path / "state.txt"
    file.write_text("before")

    before = snapshot_directory(tmp_path)

    file.write_text("after")

    after = snapshot_directory(tmp_path)

    diff = diff_snapshots(before, after)

    assert diff.modified == [Path("state.txt")]
    assert diff.created == []
    assert diff.deleted == []


def test_detects_created_file(tmp_path: Path) -> None:
    before = snapshot_directory(tmp_path)

    created = tmp_path / "new.txt"
    created.write_text("new")

    after = snapshot_directory(tmp_path)

    diff = diff_snapshots(before, after)

    assert diff.created == [Path("new.txt")]
    assert diff.modified == []
    assert diff.deleted == []


def test_detects_deleted_file(tmp_path: Path) -> None:
    deleted = tmp_path / "old.txt"
    deleted.write_text("old")

    before = snapshot_directory(tmp_path)

    deleted.unlink()

    after = snapshot_directory(tmp_path)

    diff = diff_snapshots(before, after)

    assert diff.deleted == [Path("old.txt")]
    assert diff.created == []
    assert diff.modified == []


def test_snapshot_only_hashes_requested_scope(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    observed = data / "state.json"
    ignored = tmp_path / "large.bin"
    observed.write_text('{"value": 1}', encoding="utf-8")
    ignored.write_bytes(b"before")

    before = snapshot_directory(tmp_path, include_patterns=["data/*.json"])
    observed.write_text('{"value": 2}', encoding="utf-8")
    ignored.write_bytes(b"after")
    after = snapshot_directory(tmp_path, include_patterns=["data/*.json"])

    diff = diff_snapshots(before, after)
    assert diff.modified == [Path("data/state.json")]
    assert Path("large.bin") not in before


def test_snapshot_rejects_absolute_scope(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relative"):
        snapshot_directory(tmp_path, include_patterns=[str((tmp_path / "state.json").resolve())])
