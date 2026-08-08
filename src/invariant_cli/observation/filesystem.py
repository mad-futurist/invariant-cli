from dataclasses import dataclass
from pathlib import Path
import hashlib

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

def snapshot_directory(root: Path) -> dict[Path, FileState]:
    snapshot: dict[Path, FileState] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative_path = path.relative_to(root)

        snapshot[relative_path] = FileState(
            path=relative_path,
            size=path.stat().st_size,
            digest=hash_file(path),
        )

    return snapshot

def diff_snapshots(
    before: dict[Path, FileState],
    after: dict[Path, FileState],
)-> FileSystemDiff:
    before_paths = set(before)
    after_paths = set(after)

    created = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)

    modified = sorted(
        path
        for path in before_paths & after_paths
        if before[path].digest != after[path].digest
    )

    return FileSystemDiff(
        created=created,
        modified=modified,
        deleted=deleted,
    )
    
    