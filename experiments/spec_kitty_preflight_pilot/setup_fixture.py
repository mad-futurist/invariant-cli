from __future__ import annotations

import argparse
from pathlib import Path

from experiments.spec_kitty_preflight_pilot.harness import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    setup_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create immutable Spec Kitty pilot candidates.")
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--candidate", choices=("bad", "fixed", "all"), default="all")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run `uv sync` in each candidate after creating its worktrees.",
    )
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    labels = tuple(manifest.candidates) if args.candidate == "all" else (args.candidate,)
    for label in labels:
        path = setup_candidate(args.corpus_root, manifest, label, sync=args.sync)
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
