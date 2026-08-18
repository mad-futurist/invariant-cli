from __future__ import annotations

import argparse
from pathlib import Path

from experiments.spec_kitty_preflight_pilot.harness import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    load_scenario,
    run_scenario,
    stable_json,
)

DEFAULT_COMMAND = ["uv", "run", "spec-kitty", "merge", "--dry-run"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic Spec Kitty scenario.")
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--candidate", choices=("bad", "fixed"), required=True)
    parser.add_argument("--scenario", choices=("multiple_dirty", "missing_worktree"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Candidate command after `--`; defaults to `uv run spec-kitty merge --dry-run`.",
    )
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    scenario = load_scenario(args.scenario)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    result = run_scenario(
        args.corpus_root,
        manifest,
        args.candidate,
        scenario,
        command or DEFAULT_COMMAND,
    )
    rendered = stable_json(result)
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
