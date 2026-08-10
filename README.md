# Invariant CLI

Software rewrites rarely fail because somebody translated a line of code incorrectly. They fail because the old and new systems represent the same idea in different ways, and nobody made that relationship explicit.

Invariant is an experimental CLI for exploring that problem. It runs old and new implementations, records what they change, looks for stable relationships between their observations, and checks those relationships on executions that were not used to discover them.

It is early research software, not a production verification platform. The repository is deliberately built through small, reproducible experiments.

## A small example

Imagine that an old application stores money in cents:

```text
balance_cents: 10000 -> 7000
```

The replacement stores the same balance in euros under another name:

```text
remaining: 100 -> 70
```

After seeing several paired executions, Invariant can propose this relation:

```text
target.remaining = source.balance_cents * 0.01
```

That is dynamic evidence: the values changed according to the same rule.

Invariant can also inspect simple Python usage. If the implementations contain:

```python
state["balance_cents"] -= payment_cents
account["remaining"] -= payment_eur
```

it records that both fields are read, written, and subtracted from. This does not prove that the fields mean the same thing, but it gives the candidate a second, independent piece of evidence.

The resulting candidate contract can contain both:

```yaml
evidence:
  - kind: dynamic_transition
    producer: dynamic-transition-v1
    attributes:
      matched_pairs: 3
      distinct_transitions: 3

  - kind: static_usage
    producer: python-ast-v1
    attributes:
      source_operations: [read, subtract, write]
      target_operations: [read, subtract, write]
      common_operations: [read, subtract, write]
```

The important word is **candidate**. A relation that fits a few examples is a hypothesis, not a fact. Invariant stores it explicitly and validates it against held-out executions.

## What works today

Invariant can:

- run a command and capture its process result;
- limit filesystem capture to explicit files or glob patterns;
- route changed resources through an observer registry;
- record structured changes inside JSON documents and SQLite databases;
- compare observations from two executions;
- infer JSON- and SQLite-field correspondences from several source/target execution pairs;
- discover exact and affine numeric relations;
- add simple Python AST usage evidence to dynamic candidates;
- save candidate translation contracts as YAML;
- validate candidates on executions that were not used for inference;
- report `PASS`, `FAIL`, or `INCONCLUSIVE` instead of treating missing evidence as success.

## Install

You need Python 3.12, Git, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/mad-futurist/invariant-cli.git
cd invariant-cli
uv sync
```

Check the installation:

```bash
uv run invariant --help
```

`uv run` manages the project environment for you, so activating `.venv` manually is optional.

## The current workflow

### 1. Create an Invariant workspace

Run this in the project you want to observe:

```bash
uv run invariant init --name my-project
```

Invariant creates a local `.invariant/` directory for executions, contracts, and results. It is runtime data and should not be committed.

### 2. Capture executions

Run an application through Invariant:

```bash
uv run invariant capture -- python app.py
```

You can point at another workspace explicitly:

```bash
uv run invariant capture --workspace-root /path/to/project -- python app.py
```

Every capture receives an execution ID. The stored record includes command metadata, stdout, stderr, filesystem changes, and observations produced by the available observers.

By default, capture still scans the workspace for compatibility with the early experiments. On a larger repository, limit the snapshot explicitly:

```bash
uv run invariant capture \
  --observe "data/*.json" \
  --observe "state/*.db" \
  -- python app.py
```

`--observe` accepts workspace-relative files and glob patterns and can be passed more than once. Files outside those scopes are not hashed or included in the filesystem diff.

The built-in observer registry currently recognizes JSON and SQLite resources. JSON changes are represented as document paths. SQLite changes use stable table, primary-key, and column paths such as `accounts[id=1].balance`.

### 3. Compare two executions

```bash
uv run invariant compare SOURCE_EXECUTION TARGET_EXECUTION
```

The result is `MATCH`, `DIFF`, or `INCONCLUSIVE`.

### 4. Infer a candidate contract

Inference currently requires at least three paired executions:

```bash
uv run invariant contract infer \
  --pair SOURCE_1:TARGET_1 \
  --pair SOURCE_2:TARGET_2 \
  --pair SOURCE_3:TARGET_3
```

Several pairs matter because one matching transition may be a coincidence. Repeated but varied transitions provide more useful evidence.

To add Python static-usage evidence, pass one implementation file for each side:

```bash
uv run invariant contract infer \
  --pair SOURCE_1:TARGET_1 \
  --pair SOURCE_2:TARGET_2 \
  --pair SOURCE_3:TARGET_3 \
  --source-code path/to/source/app.py \
  --target-code path/to/target/app.py
```

`--source-code` and `--target-code` must be used together. The static analyser currently recognizes string-literal dictionary access such as `state["balance"]`.

Candidate contracts are saved under `.invariant/contracts/`.

### 5. Validate with new executions

Do not validate a candidate only with the executions that produced it. Capture a new source/target pair and run:

```bash
uv run invariant contract validate \
  CONTRACT_FILE \
  --pair SOURCE_NEW:TARGET_NEW
```

A failed relation produces `FAIL`. Missing observations produce `INCONCLUSIVE`. Validation results are stored under `.invariant/results/`.

## Experiments

The `experiments/` directory contains intentionally small applications:

- `translation_contract_demo` uses different field names with the same value representation;
- `translation_transform_demo` uses different names and cents-to-euros conversion;
- `static_usage_demo` runs the complete capture/infer/validate loop and combines the cents-to-euros relation with Python AST usage evidence from differently written updates.
- `sqlite_observer_demo` runs the same inference and held-out validation pipeline against two different relational schemas, using scoped capture instead of scanning the complete workspace.

These demos are test beds for one idea at a time. Experimental code stays outside the main package until its behavior and interface are understood.

## Current limitations

Invariant does not yet understand a whole software system.

- Built-in structured observers currently support JSON and SQLite only.
- SQLite observation reads committed database files and does not yet coordinate WAL files or live database processes.
- Unscoped capture still walks the complete workspace; large projects should use `--observe`.
- Relation inference supports exact and affine numeric transformations only.
- Python static analysis is syntax-based. It does not build call graphs or follow data flow.
- Static usage enriches existing dynamic candidates; it does not create correspondences by itself.
- Candidates are not ranked or fused into a confidence score.
- There is no target-architecture model, implementation generator, or production gate system yet.

These limits are intentional. Each feature should first prove itself in a controlled experiment and produce deterministic, inspectable evidence.

## Development

Run the complete quality suite:

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src tests
```

Add dependencies with `uv add` or `uv add --dev`, then commit both `pyproject.toml` and `uv.lock`.

The main code is organized by responsibility:

```text
src/invariant_cli/
  commands/       CLI entry points
  workspace/      local Invariant workspace
  execution/      command capture and stored executions
  observation/    filesystem snapshots, observer registry, JSON and SQLite state
  comparison/     direct execution comparison
  matching/       entities, transitions, and evidence producers
  contracts/      inference, storage, enrichment, and validation
  gates/          future independent verification gates
```

## Where this is going

The long-term problem is larger than comparing two files or translating code line by line:

> Which parts of two systems correspond, what relationship connects them, which behavior must remain stable, and does the new implementation belong in the target architecture?

The capture layer is now extensible enough to test new state sources without rewriting execution orchestration. The next experiments can move toward static data flow and call context, then schema and architecture evidence. The intended end state is a translation contract supported by several independent evidence sources and enforced by reproducible gates.

## License

Apache License 2.0.
