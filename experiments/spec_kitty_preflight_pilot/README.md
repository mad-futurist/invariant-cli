# Spec Kitty pre-flight verification pilot (Verification Core)

This experiment reproduces the two review defects from Spec Kitty Feature 017 / WP02 without
modifying the Spec Kitty product repository. Invariant owns the harness; two external, detached
candidate checkouts provide the historical corpus. M1 compiles the pinned Markdown requirements
into typed Invariant specification IR and captures execution through `CaptureService` plus the
generic `GitStateProbe`. The Verification Core milestone adds a typed, human-approved FR-003
obligation and evaluates it through the generic `VerificationPlan` / `VerificationEngine` path.

The pinned candidates are:

- `0222ed3a837a6b3e1d73cd626fb0f8cf02e5e1a3`: original pre-flight implementation.
- `6985680ee5ef3b5f512cd2189d4fb8575420a571`: review fix for issue aggregation and missing
  worktrees.

`manifest.json` also pins the Feature 017 specification and WP02 prompt by ref and Git blob ID.
The FR-004 assumption is explicit: HEAD, local branches, and worktrees are protected; remote
tracking refs changed by `git fetch` are outside this pilot's mutation scope.

Both candidates set `SPEC_KITTY_CLI_VERSION=0.11.0` only for the observed command. The historical
checkout declares CLI package version 0.11.1 while its checked-in project metadata is 0.11.0;
without Spec Kitty's supported version override, execution stops before reaching pre-flight.

Setup preserves the network repository as `upstream`, then points `origin` at the local candidate
and pins both `main` and `origin/main` to its SHA. The historical implementation can still execute
`git fetch origin main`, but a moving GitHub default branch cannot inject an unrelated divergence
failure into the controlled scenarios.

## Create the corpus

Use a directory outside either repository so fixture worktrees never contaminate Invariant's Git
status:

```powershell
python -m experiments.spec_kitty_preflight_pilot.setup_fixture `
  --corpus-root C:\temp\invariant-spec-kitty-corpus `
  --sync
```

The command creates `spec-kitty-bad` and `spec-kitty-fixed`, checks out their exact commits in
detached mode, and creates WP01-WP06 branches and worktrees at the pinned candidate commit. It
never creates a product branch in Spec Kitty.

## Run the known defects

Run each scenario against both candidates:

```powershell
python -m experiments.spec_kitty_preflight_pilot.run_scenario `
  --corpus-root C:\temp\invariant-spec-kitty-corpus `
  --candidate bad `
  --scenario multiple_dirty `
  --output C:\temp\bad-multiple-dirty.json

python -m experiments.spec_kitty_preflight_pilot.run_scenario `
  --corpus-root C:\temp\invariant-spec-kitty-corpus `
  --candidate fixed `
  --scenario missing_worktree `
  --output C:\temp\fixed-missing-worktree.json
```

Repeat with `fixed`/`multiple_dirty` and `bad`/`missing_worktree` for the complete matrix. Each run
resets only harness-owned marker files and missing worktrees, applies the scenario, runs
`uv run spec-kitty merge --dry-run` from WP01, and writes a normalized record containing exit
code, output, local refs, registered worktrees, per-WP Git status, and merge-state presence before
and after execution. Unexpected candidate changes are never silently cleaned.

The pinned corpus was validated with this matrix:

| Candidate | Scenario | Observed result | Invariant verdict |
| --- | --- | --- | --- |
| bad | `multiple_dirty` | legacy check reports only WP01 | `FAIL` (WP03 missing) |
| fixed | `multiple_dirty` | pre-flight reports WP01 and WP03 | `PASS` |
| bad | `missing_worktree` | exit 0; missing WP03 is invisible | `FAIL` (WP03 missing) |
| fixed | `missing_worktree` | pre-flight reports missing WP03 | `PASS` |

In all four records, HEAD and local branch refs were unchanged and no merge state appeared. The
candidate's remote-tracking refs may change because the historical pre-flight performs `git fetch`.

Use `-- <command>` after the scenario arguments to replace the default command during harness
development. Reset both candidates with:

```powershell
python -m experiments.spec_kitty_preflight_pilot.reset_fixture `
  --corpus-root C:\temp\invariant-spec-kitty-corpus
```

M0 proved that the historical corpus is reproducible. M1 provides two normalized sides:

- `specification`: explicit FR-001 through FR-004 with `spec.md` and WP02 provenance;
- `git_before` / `git_after`: serialized views of an Invariant-native `GitStateRecord`.

The Verification Core milestone connects those sides with a safe typed assertion:

```text
FR-003
  -> SET_CONTAINS(
       scenario.blocking_work_packages,
       execution.reported_blocking_work_packages
     )
```

The mapping is explicitly recorded as `human-approved-wp02-v1`; general specification compilation
is a later milestone. Output schema v3 contains the plan, per-obligation evidence, overall verdict,
and a minimal missing-blocker counterexample. CLI integration remains out of scope until the
programmatic path is proven.

The four historical assertions can also be rerun as an opt-in test:

```powershell
$env:INVARIANT_SPEC_KITTY_CORPUS = 'C:\temp\invariant-spec-kitty-corpus'
pytest -m external_corpus tests/experiments/test_spec_kitty_preflight_external.py
```
