# Invariant CLI

Invariant is an experimental CLI for capturing and verifying software executions during migrations, rewrites, and other code transformations.

The project is currently in early development.

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
