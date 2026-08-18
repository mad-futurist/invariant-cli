from __future__ import annotations

import argparse
from pathlib import Path

from experiments.spec_kitty_preflight_pilot.harness import (
    DEFAULT_MANIFEST_PATH,
    candidate_root,
    load_manifest,
    reset_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset only pilot-owned fixture mutations.")
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--candidate", choices=("bad", "fixed", "all"), default="all")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    labels = tuple(manifest.candidates) if args.candidate == "all" else (args.candidate,)
    for label in labels:
        root = candidate_root(args.corpus_root, manifest, label)
        reset_candidate(root, manifest, label)
        print(f"reset {label}: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
