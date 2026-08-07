from pathlib import Path

import yaml

from invariant_cli.workspace.model import WorkspacePaths


class WorkspaceAlreadyExistsError(Exception):
    pass


def get_workspace_paths(root: Path) -> WorkspacePaths:
    invariant_dir = root / ".invariant"
    config = invariant_dir / "invariant.yaml"
    cases = invariant_dir / "cases"
    observations = invariant_dir / "observations"
    contracts = invariant_dir / "contracts"
    gates = invariant_dir / "gates"
    results = invariant_dir / "results"
    executions = invariant_dir / "executions"

    return WorkspacePaths(
        root=root,
        invariant_dir=invariant_dir,
        config=config,
        cases=cases,
        executions=executions,
        observations=observations,
        contracts=contracts,
        gates=gates,
        results=results,
    )


def initialize_workspace(
    root: Path,
    *,
    name: str,
    force: bool = False,
) -> WorkspacePaths:
    paths = get_workspace_paths(root)

    if paths.invariant_dir.exists():
        raise WorkspaceAlreadyExistsError(f"Workspace already exists at {paths.invariant_dir}")

    # Create the .invariant directory and subdirectories
    paths.invariant_dir.mkdir(parents=True, exist_ok=False)
    paths.cases.mkdir(exist_ok=False)
    paths.executions.mkdir(exist_ok=False)
    paths.observations.mkdir(exist_ok=False)
    paths.contracts.mkdir(exist_ok=False)
    paths.gates.mkdir(exist_ok=False)
    paths.results.mkdir(exist_ok=False)

    # Create a default config.yaml file
    default_config = {
        "name": name,
        "version": "0.1.0",
        "description": "A new invariant workspace.",
        "created_at": str(root),
        "project": {"name": name},
    }
    with open(paths.config, "w") as config_file:
        yaml.safe_dump(default_config, config_file, sort_keys=False)

    return paths


def find_workspace_root(start: Path) -> Path:
    current = start.resolve()

    for directory in (current, *current.parents):
        if (directory / ".invariant").is_dir():
            return directory

    for workspace_dir in current.rglob(".invariant"):
        if workspace_dir.is_dir():
            return workspace_dir.parent

    raise FileNotFoundError(f"No Invariant workspace found from {start}")


def load_workspace_paths(start: Path) -> WorkspacePaths:
    root = find_workspace_root(start)
    return get_workspace_paths(root)
