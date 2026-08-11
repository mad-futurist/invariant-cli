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
- collect raw changes through an extensible capture-probe lifecycle;
- normalize captured resources through JSON and SQLite decoders;
- record structured changes inside JSON documents and SQLite databases;
- compare observations from two executions;
- infer JSON- and SQLite-field correspondences from several source/target execution pairs;
- discover exact and affine numeric relations;
- infer a controlled one-to-many relation from one source field to the sum of two target fields;
- add simple Python AST usage evidence to dynamic candidates;
- block type-incompatible field pairs and bound direct and expression candidate generation;
- attach observed JSON/SQLite schema evidence to surviving hypotheses;
- group hypotheses by source, rank them deterministically, and report explicit ambiguity;
- save candidate translation contracts as YAML;
- store a versioned Evidence Graph linking entities, relations, evidence, and training runs;
- validate candidates on executions that were not used for inference;
- link validation verdicts back to the tested correspondence in the Evidence Graph;
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

Capture now has three deliberately separate steps: a runner executes the command, probes collect raw
records, and normalizers turn those records into comparable observations. The first probe watches the
filesystem; the built-in resource decoders recognize JSON and SQLite. JSON changes are represented as
document paths. SQLite changes use stable table, primary-key, and column paths such as
`accounts[id=1].balance`. This separation lets a later HTTP, database-protocol, or trace probe join the
same pipeline without being disguised as a file observer.

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

Candidate generation is bounded before relation inference. The defaults consider at most 50
schema-compatible direct targets and 100 same-scope numeric target pairs per source field. They can
be changed explicitly:

```bash
uv run invariant contract infer \
  --pair SOURCE_1:TARGET_1 \
  --pair SOURCE_2:TARGET_2 \
  --pair SOURCE_3:TARGET_3 \
  --max-direct-targets-per-source 25 \
  --max-expression-pairs-per-source 40
```

The current schema producer is deliberately observational: it derives value type, nullability,
structural parent, cardinality, primary-key path context, and identifier tokens from the captured
JSON/SQLite transitions. It does not yet read declared JSON Schema or SQLite DDL.

Candidate contracts are saved under `.invariant/contracts/`.

Every saved candidate also contains `evidence_graph` version 3. It is an inspectable graph, not a
confidence score. Its nodes represent entities, proposed correspondences, relations, evidence items,
expressions, candidate sets, and paired training executions. Edges say which entity or expression is the source or
target, which entities form an expression, which relation a candidate uses, which evidence supports
it, which ranked alternatives belong to a source candidate set, and which execution pairs produced dynamic evidence. Stable content-based IDs make the graph
deterministic even though the contract file itself receives a new UUID.

Contract format v4 keeps ordinary field-to-field candidates under `correspondences`, expression
hypotheses under `expression_correspondences`, and adds first-class `candidate_sets`. The flat lists
remain the executable validation projection; each candidate set groups both shapes under one source,
stores deterministic rank factors, and has one of these statuses:

```text
confident_candidate
ambiguous
insufficient_evidence
rejected
```

Ranking is an explanation over evidence, not an automatic truth decision. Alternatives are preserved
in the contract and Evidence Graph even when one candidate ranks higher. The first expression policy
remains intentionally small:

The initial weights are intentionally simple and visible in every candidate's `factors`: dynamic
evidence has a base of 100 plus bounded pair/transition contributions; compatible observed type adds
30; matching nullability, key context, scope, and name tokens add smaller schema contributions; every
common static operation adds 10; and an expression pays a complexity cost of 5. A tie or a top-two
distance of at most 5 produces `ambiguous`. These are deterministic ordering rules for an experiment,
not learned weights or calibrated probabilities.

```text
identity(source_field) -> sum(target_field_1, target_field_2)
```

Inference accepts it only when both target components are present and their sum follows one exact or
affine relation across every training pair. Existing pairwise contracts remain loadable.

### 5. Validate with new executions

Do not validate a candidate only with the executions that produced it. Capture a new source/target pair and run:

```bash
uv run invariant contract validate \
  CONTRACT_FILE \
  --pair SOURCE_NEW:TARGET_NEW
```

A failed relation produces `FAIL`. Missing observations produce `INCONCLUSIVE`. Validation results are
stored under `.invariant/results/`. Their Evidence Graph extends the candidate graph with held-out
validation-pair and validation nodes, including `validates` links back to the correspondence under test.

## Experiments

The `experiments/` directory contains intentionally small applications:

- `translation_contract_demo` uses different field names with the same value representation;
- `translation_transform_demo` uses different names and cents-to-euros conversion;
- `static_usage_demo` runs the complete capture/infer/validate loop and combines the cents-to-euros relation with Python AST usage evidence from differently written updates.
- `sqlite_observer_demo` runs the same inference and held-out validation pipeline against two different relational schemas, using scoped capture instead of scanning the complete workspace.
- `cross_representation_demo` proves that the shared capture and matching pipeline can infer and validate a cents-to-euros relation from SQLite on one side and JSON on the other; it also checks both candidate and validation Evidence Graphs.
- `one_to_many_demo` varies how one SQLite balance is split across two JSON fields, proving that neither component matches independently while their sum produces and validates one expression correspondence.
- `ambiguity_ranking_demo` gives one source two indistinguishable targets and proves that both alternatives survive inference and held-out validation with an explicit `ambiguous` status.

These demos are test beds for one idea at a time. Experimental code stays outside the main package until its behavior and interface are understood.

## Current limitations

Invariant does not yet understand a whole software system.

- Built-in structured observers currently support JSON and SQLite only.
- SQLite observation reads committed database files and does not yet coordinate WAL files or live database processes.
- Unscoped capture still walks the complete workspace; large projects should use `--observe`.
- Relation inference supports exact and affine numeric transformations only.
- Expression inference currently supports one source component and exactly two summed target components.
- Candidate generation uses fixed configurable bounds; a bound that is too small can exclude a valid hypothesis and must be reported as an inference assumption.
- Python static analysis is syntax-based. It does not build call graphs or follow data flow.
- Static usage enriches existing dynamic candidates; it does not create correspondences by itself.
- Observed schema evidence does not yet inspect declared JSON Schema, SQLite DDL, foreign keys, or indexes.
- Candidate scores are deterministic ordering factors, not calibrated probabilities or confidence scores.
- Evidence Graph v3 is embedded in saved artifacts and is not yet queryable through a CLI command.
- Dynamic evidence currently points to paired executions as a whole; it does not yet store individual observed-transition nodes.
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
  execution/      command runner and stored executions
  capture/        probe lifecycle, raw records, and observation normalization
  observation/    filesystem snapshots and JSON/SQLite resource decoders
  comparison/     direct execution comparison
  matching/       entities, transitions, and evidence producers
  evidence/       Evidence Graph model and deterministic graph builders
  contracts/      inference, storage, enrichment, and validation
  gates/          future independent verification gates
```

## Where this is going

The long-term problem is larger than comparing two files or translating code line by line:

> Which parts of two systems correspond, what relationship connects them, which behavior must remain stable, and does the new implementation belong in the target architecture?

The contract model now handles pairwise and a first one-to-many relation, while Candidate Sets and
Evidence Graph v3 make ambiguity inspectable without deleting alternatives. The strongest next stage
is richer independent evidence: declared schema and database constraints, then bounded static data
flow and call context. Those signals can strengthen or challenge the current ranking before entity
kinds expand toward endpoints, events, components, and target-architecture constraints.

## License

Apache License 2.0.
