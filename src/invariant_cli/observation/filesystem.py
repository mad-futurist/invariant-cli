import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    ".invariant",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


@dataclass(frozen=True)
class FileState:
    path: Path
    size: int
    digest: str


@dataclass(frozen=True)
class FileSystemDiff:
    created: list[Path]
    deleted: list[Path]
    modified: list[Path]


def hash_file(path: Path) -> str:
    """Compute the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def snapshot_directory(
    root: Path,
    *,
    include_patterns: list[str] | None = None,
) -> dict[Path, FileState]:
    snapshot: dict[Path, FileState] = {}

    for path in _candidate_files(root, include_patterns):
        if not path.is_file():
            continue

        relative_path = path.relative_to(root)

        if any(part in IGNORED_DIRECTORIES for part in relative_path.parts):
            continue

        snapshot[relative_path] = FileState(
            path=relative_path,
            size=path.stat().st_size,
            digest=hash_file(path),
        )

    return snapshot


def _candidate_files(root: Path, include_patterns: list[str] | None) -> Iterable[Path]:
    if not include_patterns:
        yield from root.rglob("*")
        return

    resolved_root = root.resolve()
    seen: set[Path] = set()

    for raw_pattern in include_patterns:
        pattern = raw_pattern.replace("\\", "/")

        if Path(pattern).is_absolute():
            raise ValueError(f"Observe pattern must be relative to the workspace: {raw_pattern}")

        for candidate in root.glob(pattern):
            paths = candidate.rglob("*") if candidate.is_dir() else (candidate,)

            for path in paths:
                try:
                    path.resolve().relative_to(resolved_root)
                except ValueError:
                    continue

                if path not in seen:
                    seen.add(path)
                    yield path


def diff_snapshots(
    before: dict[Path, FileState],
    after: dict[Path, FileState],
) -> FileSystemDiff:
    before_paths = set(before)
    after_paths = set(after)

    created = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)

    modified = sorted(
        path for path in before_paths & after_paths if before[path].digest != after[path].digest
    )

    return FileSystemDiff(
        created=created,
        modified=modified,
        deleted=deleted,
    )
