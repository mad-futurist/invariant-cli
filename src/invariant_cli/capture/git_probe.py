from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from invariant_cli.capture.model import (
    CaptureContext,
    GitState,
    GitStateRecord,
    GitWorktreeState,
    ProbeResult,
)
from invariant_cli.capture.probe import ProbeSession
from invariant_cli.execution.model import Execution


class GitProbeError(RuntimeError):
    """Raised when a Git state snapshot cannot be established."""


class GitStateProbe:
    def __init__(
        self,
        *,
        repository_root: Path,
        expected_worktrees: Mapping[str, Path] | None = None,
    ) -> None:
        self._repository_root = repository_root.resolve()
        self._expected_worktrees = dict(expected_worktrees or {})

    def start(self, context: CaptureContext) -> ProbeSession:
        before = read_git_state(
            self._repository_root,
            working_directory=context.working_directory,
            expected_worktrees=self._expected_worktrees,
        )
        return _GitStateProbeSession(
            repository_root=self._repository_root,
            working_directory=context.working_directory,
            expected_worktrees=self._expected_worktrees,
            before=before,
        )


class _GitStateProbeSession:
    def __init__(
        self,
        *,
        repository_root: Path,
        working_directory: Path,
        expected_worktrees: Mapping[str, Path],
        before: GitState,
    ) -> None:
        self._repository_root = repository_root
        self._working_directory = working_directory
        self._expected_worktrees = expected_worktrees
        self._before = before

    def stop(self, execution: Execution) -> ProbeResult:
        del execution
        after = read_git_state(
            self._repository_root,
            working_directory=self._working_directory,
            expected_worktrees=self._expected_worktrees,
        )
        return ProbeResult(records=[GitStateRecord(before=self._before, after=after)])


def read_git_state(
    repository_root: Path,
    *,
    working_directory: Path,
    expected_worktrees: Mapping[str, Path] | None = None,
) -> GitState:
    repository_root = repository_root.resolve()
    working_directory = working_directory.resolve()
    _require_repository(repository_root)
    local_branches = _read_local_branches(repository_root)
    worktrees = _read_worktrees(repository_root)
    expected_status = {
        identifier: _status(path.resolve()) if path.resolve().is_dir() else None
        for identifier, path in sorted((expected_worktrees or {}).items())
    }
    merge_path = Path(
        _git(["rev-parse", "--git-path", "MERGE_HEAD"], cwd=working_directory).stdout.strip()
    )
    if not merge_path.is_absolute():
        merge_path = working_directory / merge_path
    return GitState(
        head=_git(["rev-parse", "HEAD"], cwd=repository_root).stdout.strip(),
        current_branch=_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=working_directory
        ).stdout.strip(),
        local_branches=local_branches,
        worktrees=worktrees,
        expected_worktree_status=expected_status,
        merge_in_progress=merge_path.exists(),
    )


def _read_local_branches(repository_root: Path) -> dict[str, str]:
    output = _git(
        ["for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"],
        cwd=repository_root,
    ).stdout
    branches: dict[str, str] = {}
    for line in output.splitlines():
        name, sha = line.split(" ", maxsplit=1)
        branches[name] = sha
    return dict(sorted(branches.items()))


def _read_worktrees(repository_root: Path) -> tuple[GitWorktreeState, ...]:
    output = _git(["worktree", "list", "--porcelain"], cwd=repository_root).stdout
    states: list[GitWorktreeState] = []
    current: dict[str, str] = {}
    for line in [*output.splitlines(), ""]:
        if not line:
            if current:
                absolute_path = Path(current["worktree"])
                states.append(
                    GitWorktreeState(
                        path=_normalized_path(absolute_path, repository_root),
                        head=current.get("HEAD", ""),
                        branch=current.get("branch", "").removeprefix("refs/heads/") or None,
                        status=_status(absolute_path),
                    )
                )
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return tuple(sorted(states, key=lambda state: state.path))


def _status(worktree: Path) -> tuple[str, ...]:
    return tuple(_git(["status", "--porcelain"], cwd=worktree).stdout.splitlines())


def _normalized_path(path: Path, repository_root: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repository_root)
    except ValueError:
        return resolved.as_posix()
    return "." if not relative.parts else relative.as_posix()


def _require_repository(path: Path) -> None:
    result = _git(["rev-parse", "--is-inside-work-tree"], cwd=path, check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise GitProbeError(f"Not a Git working tree: {path}")


def _git(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        rendered = " ".join(args)
        raise GitProbeError(f"Git command failed ({completed.returncode}): {rendered}\n{detail}")
    return completed


__all__ = ["GitProbeError", "GitStateProbe", "read_git_state"]
