from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PILOT_ROOT = Path(__file__).parent
DEFAULT_MANIFEST_PATH = PILOT_ROOT / "manifest.json"
SCENARIO_ROOT = PILOT_ROOT / "scenarios"
DIRTY_MARKER = ".invariant-pilot-dirty"


@dataclass(frozen=True)
class Candidate:
    label: str
    directory: str
    sha: str
    environment: dict[str, str]


@dataclass(frozen=True)
class PilotManifest:
    repository: str
    feature: str
    work_package: str
    expected_work_packages: tuple[str, ...]
    candidates: dict[str, Candidate]
    raw: dict[str, Any]


@dataclass(frozen=True)
class Scenario:
    id: str
    current_work_package: str
    dirty_work_packages: tuple[str, ...]
    missing_work_packages: tuple[str, ...]
    requirements: tuple[str, ...]


class HarnessError(RuntimeError):
    """Raised when a corpus fixture cannot be manipulated safely."""


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> PilotManifest:
    raw = _read_json(path)
    if raw.get("schema_version") != 1:
        raise HarnessError(f"Unsupported manifest schema: {raw.get('schema_version')!r}")
    mission = _mapping(raw, "mission")
    upstream = _mapping(raw, "upstream")
    raw_candidates = _mapping(raw, "candidates")
    candidates = {
        label: Candidate(
            label,
            str(value["directory"]),
            str(value["sha"]),
            {str(key): str(item) for key, item in value.get("environment", {}).items()},
        )
        for label, value in raw_candidates.items()
        if isinstance(value, dict)
    }
    if not candidates:
        raise HarnessError("The manifest does not define any candidates.")
    return PilotManifest(
        repository=str(upstream["repository"]),
        feature=str(mission["feature"]),
        work_package=str(mission["work_package"]),
        expected_work_packages=tuple(str(item) for item in mission["expected_work_packages"]),
        candidates=candidates,
        raw=raw,
    )


def load_scenario(name: str, root: Path = SCENARIO_ROOT) -> Scenario:
    raw = _read_json(root / f"{name}.json")
    if raw.get("schema_version") != 1:
        raise HarnessError(f"Unsupported scenario schema: {raw.get('schema_version')!r}")
    return Scenario(
        id=str(raw["id"]),
        current_work_package=str(raw["current_work_package"]),
        dirty_work_packages=tuple(str(item) for item in raw["dirty_work_packages"]),
        missing_work_packages=tuple(str(item) for item in raw["missing_work_packages"]),
        requirements=tuple(str(item) for item in raw["requirements"]),
    )


def setup_candidate(
    corpus_root: Path,
    manifest: PilotManifest,
    label: str,
    *,
    sync: bool = False,
) -> Path:
    candidate = _candidate(manifest, label)
    candidate_root = (corpus_root / candidate.directory).resolve()
    corpus_root.mkdir(parents=True, exist_ok=True)
    if not candidate_root.exists():
        _run(["git", "clone", manifest.repository, str(candidate_root)], cwd=corpus_root)
    _require_git_repository(candidate_root)
    if not _commit_exists(candidate_root, candidate.sha):
        _run(["git", "fetch", "origin", candidate.sha], cwd=candidate_root)
    _run(["git", "checkout", "--detach", candidate.sha], cwd=candidate_root)
    _assert_candidate_head(candidate_root, candidate)
    _verify_artifacts(candidate_root, manifest)
    _exclude_invariant_artifacts(candidate_root)
    _ensure_worktrees(candidate_root, manifest, candidate)
    if sync:
        _run(["uv", "sync"], cwd=candidate_root)
    return candidate_root


def reset_candidate(candidate_root: Path, manifest: PilotManifest, label: str) -> None:
    candidate = _candidate(manifest, label)
    candidate_root = candidate_root.resolve()
    _require_git_repository(candidate_root)
    _assert_candidate_head(candidate_root, candidate)
    _ensure_worktrees(candidate_root, manifest, candidate)
    for wp_id in manifest.expected_work_packages:
        worktree = _worktree_path(candidate_root, manifest.feature, wp_id)
        marker = worktree / DIRTY_MARKER
        if marker.exists():
            marker.unlink()
        status = _git(["status", "--porcelain"], cwd=worktree).stdout.strip()
        if status:
            raise HarnessError(f"Refusing to clean unexpected changes in {worktree}:\n{status}")


def apply_scenario(
    candidate_root: Path,
    manifest: PilotManifest,
    scenario: Scenario,
) -> Path:
    expected = set(manifest.expected_work_packages)
    mentioned = {
        scenario.current_work_package,
        *scenario.dirty_work_packages,
        *scenario.missing_work_packages,
    }
    unknown = sorted(mentioned - expected)
    if unknown:
        raise HarnessError(f"Scenario references unknown work packages: {unknown}")
    reset_candidate(candidate_root, manifest, _candidate_label(candidate_root, manifest))
    for wp_id in scenario.dirty_work_packages:
        marker = _worktree_path(candidate_root, manifest.feature, wp_id) / DIRTY_MARKER
        marker.write_text(f"dirty fixture for {wp_id}\n", encoding="utf-8")
    for wp_id in scenario.missing_work_packages:
        worktree = _worktree_path(candidate_root, manifest.feature, wp_id)
        _git(["worktree", "remove", "--force", str(worktree)], cwd=candidate_root)
    current = _worktree_path(candidate_root, manifest.feature, scenario.current_work_package)
    if not current.is_dir():
        raise HarnessError(f"Current worktree is missing: {current}")
    return current


def run_scenario(
    corpus_root: Path,
    manifest: PilotManifest,
    label: str,
    scenario: Scenario,
    command: list[str],
) -> dict[str, object]:
    if not command:
        raise HarnessError("The candidate command cannot be empty.")
    candidate = _candidate(manifest, label)
    candidate_root = (corpus_root / candidate.directory).resolve()
    _assert_candidate_head(candidate_root, candidate)
    working_directory = apply_scenario(candidate_root, manifest, scenario)
    before = git_snapshot(candidate_root, manifest, working_directory)
    completed = _run(
        command,
        cwd=working_directory,
        check=False,
        environment=candidate.environment,
    )
    after = git_snapshot(candidate_root, manifest, working_directory)
    return {
        "schema_version": 1,
        "scenario": scenario.id,
        "requirements": list(scenario.requirements),
        "candidate": {"label": label, "ref": candidate.sha},
        "command": command,
        "execution": {
            "exit_code": completed.returncode,
            "stdout": _normalize_text(completed.stdout, candidate_root),
            "stderr": _normalize_text(completed.stderr, candidate_root),
        },
        "git_before": before,
        "git_after": after,
    }


def git_snapshot(
    candidate_root: Path,
    manifest: PilotManifest,
    working_directory: Path,
) -> dict[str, object]:
    refs = {}
    raw_refs = _git(
        ["for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"],
        cwd=candidate_root,
    ).stdout
    for line in raw_refs.splitlines():
        name, sha = line.split(" ", maxsplit=1)
        refs[name] = sha
    worktrees = _parse_worktrees(candidate_root)
    statuses: dict[str, list[str] | None] = {}
    for wp_id in manifest.expected_work_packages:
        path = _worktree_path(candidate_root, manifest.feature, wp_id)
        statuses[wp_id] = (
            _git(["status", "--porcelain"], cwd=path).stdout.splitlines() if path.is_dir() else None
        )
    merge_path = Path(
        _git(["rev-parse", "--git-path", "MERGE_HEAD"], cwd=working_directory).stdout.strip()
    )
    if not merge_path.is_absolute():
        merge_path = working_directory / merge_path
    return {
        "head": _git(["rev-parse", "HEAD"], cwd=candidate_root).stdout.strip(),
        "current_branch": _git(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=working_directory
        ).stdout.strip(),
        "local_branches": dict(sorted(refs.items())),
        "worktrees": worktrees,
        "worktree_status": statuses,
        "merge_in_progress": merge_path.exists(),
    }


def candidate_root(corpus_root: Path, manifest: PilotManifest, label: str) -> Path:
    return (corpus_root / _candidate(manifest, label).directory).resolve()


def stable_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _ensure_worktrees(
    candidate_root: Path,
    manifest: PilotManifest,
    candidate: Candidate,
) -> None:
    _git(["worktree", "prune"], cwd=candidate_root)
    registered = {item["path"]: item for item in _parse_worktrees(candidate_root)}
    for wp_id in manifest.expected_work_packages:
        branch = f"{manifest.feature}-{wp_id}"
        worktree = _worktree_path(candidate_root, manifest.feature, wp_id)
        branch_ref = f"refs/heads/{branch}"
        branch_sha = _git(
            ["show-ref", "--verify", "--hash", branch_ref],
            cwd=candidate_root,
            check=False,
        ).stdout.strip()
        if branch_sha and branch_sha != candidate.sha:
            raise HarnessError(
                f"Refusing to move fixture branch {branch}: {branch_sha} != {candidate.sha}"
            )
        if not branch_sha:
            _git(["branch", branch, candidate.sha], cwd=candidate_root)
        normalized = _normalized_path(worktree, candidate_root)
        if normalized in registered:
            worktree_state = registered[normalized]
            if worktree_state["branch"] != branch or worktree_state["head"] != candidate.sha:
                raise HarnessError(f"Unexpected worktree state at {worktree}: {worktree_state}")
        else:
            if worktree.exists():
                raise HarnessError(f"Unregistered worktree path already exists: {worktree}")
            worktree.parent.mkdir(parents=True, exist_ok=True)
            _git(["worktree", "add", str(worktree), branch], cwd=candidate_root)


def _parse_worktrees(candidate_root: Path) -> list[dict[str, str]]:
    output = _git(["worktree", "list", "--porcelain"], cwd=candidate_root).stdout
    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in [*output.splitlines(), ""]:
        if not line:
            if current:
                path = Path(current["worktree"])
                items.append(
                    {
                        "path": _normalized_path(path, candidate_root),
                        "head": current.get("HEAD", ""),
                        "branch": current.get("branch", "(detached)").removeprefix("refs/heads/"),
                    }
                )
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return sorted(items, key=lambda item: item["path"])


def _normalized_path(path: Path, candidate_root: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(candidate_root.resolve())
    except ValueError:
        return resolved.as_posix()
    return "." if not relative.parts else relative.as_posix()


def _normalize_text(text: str, candidate_root: Path) -> str:
    variants = {
        str(candidate_root),
        str(candidate_root).replace("\\", "/"),
    }
    normalized = text
    for variant in sorted(variants, key=len, reverse=True):
        normalized = normalized.replace(variant, "<candidate>")
    return normalized.replace("\r\n", "\n")


def _exclude_invariant_artifacts(candidate_root: Path) -> None:
    common_dir_text = _git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=candidate_root
    ).stdout.strip()
    exclude = Path(common_dir_text) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if ".invariant/" not in existing.splitlines():
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        exclude.write_text(f"{existing}{prefix}.invariant/\n", encoding="utf-8")


def _verify_artifacts(candidate_root: Path, manifest: PilotManifest) -> None:
    artifacts = manifest.raw.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise HarnessError("Expected 'artifacts' to be an array.")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise HarnessError("Each pinned artifact must be an object.")
        path = str(artifact["path"])
        ref = str(artifact["ref"])
        expected = str(artifact["git_blob_sha1"])
        if not _commit_exists(candidate_root, ref):
            _run(["git", "fetch", "origin", ref], cwd=candidate_root)
        actual = _git(["rev-parse", f"{ref}:{path}"], cwd=candidate_root).stdout.strip()
        if actual != expected:
            raise HarnessError(
                f"Pinned artifact mismatch for {path} at {ref}: {actual} != {expected}"
            )


def _candidate(manifest: PilotManifest, label: str) -> Candidate:
    try:
        return manifest.candidates[label]
    except KeyError as exc:
        raise HarnessError(f"Unknown candidate {label!r}.") from exc


def _candidate_label(candidate_root: Path, manifest: PilotManifest) -> str:
    resolved = candidate_root.resolve()
    for label, candidate in manifest.candidates.items():
        if resolved.name == Path(candidate.directory).name:
            return label
    raise HarnessError(f"Candidate directory is not declared in the manifest: {resolved}")


def _assert_candidate_head(candidate_root: Path, candidate: Candidate) -> None:
    _require_git_repository(candidate_root)
    actual = _git(["rev-parse", "HEAD"], cwd=candidate_root).stdout.strip()
    if actual != candidate.sha:
        raise HarnessError(
            f"Candidate {candidate.label} is not pinned at {candidate.sha}; found {actual}."
        )


def _require_git_repository(path: Path) -> None:
    if not path.is_dir():
        raise HarnessError(f"Candidate directory does not exist: {path}")
    result = _git(["rev-parse", "--is-inside-work-tree"], cwd=path, check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise HarnessError(f"Not a Git working tree: {path}")


def _commit_exists(candidate_root: Path, sha: str) -> bool:
    return (
        _git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd=candidate_root, check=False).returncode
        == 0
    )


def _worktree_path(candidate_root: Path, feature: str, wp_id: str) -> Path:
    return candidate_root / ".worktrees" / f"{feature}-{wp_id}"


def _git(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], cwd=cwd, check=check)


def _run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_environment = None
    if environment:
        process_environment = {**os.environ, **environment}
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=process_environment,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        rendered = " ".join(command)
        raise HarnessError(f"Command failed ({completed.returncode}): {rendered}\n{detail}")
    return completed


def _mapping(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise HarnessError(f"Expected {key!r} to be an object.")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"Cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"Expected a JSON object in {path}.")
    return value
