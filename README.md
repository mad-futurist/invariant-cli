# Invariant CLI

Invariant is an experimental CLI for checking what happens to software behavior when a system is rewritten, migrated, or reorganized.

The basic idea is simple: run the old and new implementations, capture what they actually do, and look for stable relations between the two.

Invariant is still early. It is not a production verification system yet. The repository is currently used to build and test the core pieces of that workflow.

## What works today

Invariant can:

- run a command and capture its execution;
- record process information and filesystem changes;
- observe changes inside JSON files;
- compare observations from two executions;
- infer candidate correspondences from several paired source/target executions;
- detect exact value relations and simple affine transformations;
- validate an inferred candidate contract on executions that were not used to infer it.

For example, the source implementation may store a balance as cents:

```
balance_cents: 10000 → 7000
```

while the target implementation stores the same state as euros:

```
remaining: 100 → 70
```

Given several paired executions, Invariant can infer the candidate relation:

```
target = source × 0.01
```

and then check that relation on a new execution.

The important word here is **candidate**. Invariant does not treat a relation as true just because it fits a few examples. Inferred relations are kept as explicit artifacts and can be validated against additional executions.

## Setup

You need Python 3.12, Git, and `uv`.

Clone the repository:

```
git clone https://github.com/mad-futurist/invariant-cli.git
cd invariant-cli
```

Install the project dependencies:

```
uv sync
```

You do not need to activate the virtual environment manually. Commands can be run with `uv run`.

Check that the CLI works:

```
uv run invariant --help
```

## Initialize a workspace

```
uv run invariant init --name my-project
```

Invariant creates a local `.invariant` directory:

```
.invariant/
├── invariant.yaml
├── executions/
├── contracts/
├── gates/
└── results/
```

The directory contains local execution and verification artifacts and is not meant to be committed.

## Capture an execution

```
uv run invariant capture -- python app.py
```

You can also point it at a workspace explicitly:

```
uv run invariant capture --workspace-root /path/to/project -- python app.py
```

Each capture receives an execution ID and is stored under `.invariant/executions/`.

An execution records process metadata, stdout/stderr, filesystem changes, and observations produced by the available observers. JSON files are currently the first structured observation source.

## Compare executions

```
uv run invariant compare SOURCE_EXECUTION TARGET_EXECUTION
```

A comparison can produce `MATCH`, `DIFF`, or `INCONCLUSIVE`.

`INCONCLUSIVE` is used when there is not enough comparable observation data. An absence of detected differences is not automatically treated as proof of equivalence.

## Infer a candidate translation contract

```
uv run invariant contract infer \
    --pair SOURCE_1:TARGET_1 \
    --pair SOURCE_2:TARGET_2 \
    --pair SOURCE_3:TARGET_3
```

Using several pairs matters. A value that happens to be equal once is weak evidence; a relation that remains stable across different transitions is more interesting.

Candidate contracts are written to `.invariant/contracts/`.

A candidate may contain a direct relation:

```
source/state.json#balance
    ↔
target/account.json#remaining
```

or a transformation:

```
source/state.json#balance_cents  × 0.01  ↔  target/account.json#remaining
```

The current relation inference supports exact and affine numeric relations. More forms of evidence and matching will be added incrementally.

## Validate a candidate contract

The executions used for inference should not also be the only validation data. Capture a new source/target pair and run:

```
uv run invariant contract validate CONTRACT_FILE --pair SOURCE_NEW:TARGET_NEW
```

Validation produces `PASS`, `FAIL`, or `INCONCLUSIVE`.

This gives a simple experimental loop:

```
source executions ─┐
                   ├── infer ── candidate contract
target executions ─┘                 │
                                     ▼
                            held-out executions
                                     │
                                     ▼
                              validate relation
```

## Experiments

Experimental applications live under `experiments/`. They are intentionally small — their job is to make one verification problem easy to reproduce.

Current experiments include different source/target field names and different numeric representations (cents vs. euros).

## Development

```
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src tests
```

Add a runtime dependency:

```
uv add <package>
```

Add a development dependency:

```
uv add --dev <package>
```

Commit both `pyproject.toml` and `uv.lock` after dependency changes.

## Repository structure

```
src/invariant_cli/
├── commands/
├── workspace/
├── execution/
├── observation/
├── matching/
├── comparison/
├── contracts/
├── gates/
├── adapters/
└── reporting/

tests/
experiments/
```

## Where this is going

The current experiments only use a small part of what a translation contract may eventually contain.

A real software migration can change file formats, database schemas, service boundaries, APIs, event flows, ownership, and architecture while still preserving the behavior that matters.

The longer-term problem Invariant is exploring is therefore not simply:

```
Are these two files equal?
```

but:

```
Which parts of these two systems correspond,
what relation connects them,
and does that relation continue to hold?
```

The project is being built around that question one reproducible experiment at a time.

## License

Apache License 2.0.

## Requirements

* Python 3.12
* [uv](https://docs.astral.sh/uv/)
* Git

## Setup

Clone the repository:

```bash
git clone <repository-url>
cd invariant-cli
```

Install `uv` if you do not already have it.

### Windows

```powershell
winget install --id=astral-sh.uv -e
```

### macOS / Linux

Follow the installation instructions from the uv documentation:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Check that it is available:

```bash
uv --version
```

## Install dependencies

The project uses `uv` for dependency and virtual environment management.

Run:

```bash
uv sync
```

This will:

* create `.venv` if it does not exist;
* install the Python version required by the project when needed;
* install dependencies from `pyproject.toml`;
* use the exact versions recorded in `uv.lock`.

You normally do not need to activate the virtual environment manually. Commands can be run through `uv run`.

For example:

```bash
uv run invariant --help
```

If you prefer to activate the environment manually:

### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
source .venv/bin/activate
```

## Run the CLI

Show available commands:

```bash
uv run invariant --help
```

Initialize Invariant in a project:

```bash
uv run invariant init --name my-project
```

This creates a `.invariant` directory in the project.

Example:

```text
.invariant/
├── invariant.yaml
├── executions/
├── observations/
├── contracts/
├── gates/
└── results/
```

## Capture an execution

Invariant can run an existing command and store information about its execution.

Example:

```bash
uv run invariant capture -- python app.py
```

Run capture from any directory by explicitly providing the workspace root
(the folder that directly contains `.invariant`):

```bash
uv run invariant capture --workspace-root /path/to/project -- python app.py
```

When `--workspace-root` is provided, Invariant executes the command from that
root and computes filesystem snapshots there.

For a simple test:

```bash
uv run invariant capture -- python -c "print('Hello from Invariant')"
```

The captured execution is stored under:

```text
.invariant/executions/
```

At the moment an execution contains basic process information such as:

* executed command;
* working directory;
* start and finish time;
* duration;
* exit code;
* stdout;
* stderr.

More runtime observations will be added as the capture layer develops.

## Tests

Run the test suite:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

Run formatting:

```bash
uv run ruff format .
```

Run type checking:

```bash
uv run mypy src tests
```

## Project structure

```text
src/invariant_cli/
├── commands/
├── workspace/
├── execution/
├── observation/
├── contracts/
├── gates/
├── adapters/
└── reporting/

tests/
experiments/
pilots/
docs/
```

Stable CLI and library code lives under `src/invariant_cli`.

Experimental work should stay under `experiments/` until the interface and behavior are sufficiently understood to move into the main package.

Partner-specific work and reproducible pilot material should stay under `pilots/`.

## Dependency management

Add a runtime dependency with:

```bash
uv add <package>
```

Example:

```bash
uv add pyyaml
```

Add a development dependency with:

```bash
uv add --dev <package>
```

Example:

```bash
uv add --dev pytest
```

After changing dependencies, commit both:

```text
pyproject.toml
uv.lock
```

Do not commit `.venv`.

## Development status

Invariant is currently being built around a small set of primitives:

```text
workspace
    ↓
execution capture
    ↓
observations
    ↓
specifications / verification obligations
    ↓
gates
    ↓
results and counterexamples
```

The current focus is execution capture and the representation of observable software behavior.
