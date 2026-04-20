---
name: metric-design
description: Use this skill when the user wants the LLM to author a new Coverage Cube MetricPlugin by reading the cube's current state and proposing a new measurement that reveals a latent dimension of cube state not currently surfaced. This skill is generative, contextual, and bound to the contextual-skill pattern (create-datum + semantic-balance obligations, four-piece protocol). Metrics are *reveal-pressure* modules — they do not ingest new material; they compute over IR state and emit MetricResult + datum instances. Invoke when the user says "add a new metric", "measure <X> on the cube", "I want to know how <Y> is distributed", "surface <Z> pressure", "author a metric for <W>". Do NOT invoke when the user wants to RUN existing metrics — that is `cube`. Do NOT invoke for new source ingestion — that is `adapter-design`. Keywords: metric design, metric plugin, MetricPlugin, MetricResult, fires_at, measurement, reveal pressure, cube state metric, custom metric, metric authoring, metric proof.
---

# Metric-Design Skill — Contextual, Generative, Reveal-Pressure

A module-authoring skill under the contextual-skill pattern. Authors a new `MetricPlugin` as a **contextual move on the cube** — read current state, reveal a dimension not currently surfaced, emit both a `MetricResult` AND typed datum instances, and ship the four proofs + network-extension report + balance check.

| Skill | Answers |
|---|---|
| `cube` | Run / display existing metrics. |
| `adapter-design` | Bring new source material onto the substrate. |
| `metric-design` | **Reveal a latent dimension of existing cube state.** |
| `datum-design` | Define a typed claim derived from signals. |
| `knowledge-shape` | Transform cube knowledge into a different representation. |

## Where metrics sit (reveal-pressure)

Adapters **create** pressure: they bring new candidates onto cells, expanding the measurement surface. Metrics **reveal** latent pressure already present: they compute over `KnowledgeIR` state and surface patterns the substrate already carries but nobody was reading yet.

- `coverage.py` reveals the ratio of placed vs empty cells per rank.
- `vacuum.py` reveals specifically *which* cells are empty — the untested-territory signal.
- `frustration.py` reveals H⁰-disagreement on edges — "unit tests pass but integration would fail" before anyone writes the integration test.
- `richness.py` reveals candidate diversity per cell — is the cell single-source-dominated or multi-source-balanced?

A new metric must add a *distinct* reveal — it cannot duplicate an existing metric's signal. This is the intent-as-pressure discipline at the metric level.

## The two obligations

Every invocation of this skill **must** fulfill both or refuse to ship:

1. **create-datum** — the authored metric's PROOF must ship a `datum_runner` that produces typed, cited datum instances. The metric doesn't just emit a `MetricResult` with scalars — it emits claims citing specific cells, severity, and recommended action.

2. **semantic-balance** — the metric must fire on a *balanced subset* of the cube. Firing on every cell is noise; firing on none is useless. The balance check projects how many cells would fire on a representative IR state and flags concentration.

## The four framed pieces

### Piece 1 — Requirements for the LLM (the contract)

The metric the LLM writes must satisfy:

- **Protocol**: `s3/cubes/metrics/base.py::MetricPlugin` — `name: str`, `fires_at: frozenset[str]`, `measure(ir) -> MetricResult`.
- **`fires_at` subset of allowed values**: `{"ingest", "accept", "reject", "modify", "sweep", "ci", "post-deploy", "ide"}`.
- **`MetricResult`**: `name`, `scalars` (named numbers), `cell_readings` (per-cell dict), `summary` (one-line).
- **PROOF**: module-level `ProofDeclaration` — pressure_claim names the reveal-dimension; datum_runner emits typed datum instances; corrective_runner demonstrates measurable shift when a cell is marked `intentionally_<state>`; dual test covers `measure()` + skill-vs-code reload.
- **Test module**: `run() -> dict` + `run_skill_test(fixture_path) -> dict`.
- **Fixture**: a minimal IR state exercising the metric — placements chosen to make the pressure claim fire with ≥1 datum instance.
- **Distinctness**: the metric's reveal must not duplicate an existing metric's cell_readings pattern. If it would, extend the existing metric (new scalar / new rank) rather than author a new module.

### Piece 2 — Generative engine (contextual authorship flow)

**Step 0 — Read the target reveal gap.** What dimension of cube state is the user pointing at that current metrics don't surface? Examples: "I want to know which cells are frustrated AND high-rank," "I want to know per-source richness," "I want to measure recency of last placement per cell." Name the gap.

**Step 1 — Read cube context.** Call `s3.cubes.skill_support.read_cube_context(ir)`. Capture placed cells, vacuum cells, load distribution, axis convention. The metric you author should *use* this context — if the cube has almost all cells placed, a "vacuum" variant is less interesting than a "load-concentration" variant. Context shapes the metric.

**Step 2 — Diff against existing metrics.** Iterate `s3/cubes/metrics/` modules. For each, read `measure()`'s scalars and cell_readings shape. Confirm your proposed metric has a *distinct* cell_readings axis. If not, amend an existing metric rather than author a new one.

**Step 3 — Name the pressure claim.** One sentence in cell / rank / datum language: *"MyMetric reveals <reveal-dimension> on cells of rank <r> where <condition>."* No external-system vocabulary.

**Step 4 — Pick `fires_at`.** Which lifecycle events should trigger this metric? `ingest` = every adapter run; `accept` / `reject` / `modify` = every placement decision; `sweep` = orbit sweeps; `ci` = pre-merge; `ide` = during authoring. Choose the narrowest meaningful set. Over-firing breaks balance.

**Step 5 — Author the metric module.** `s3/cubes/metrics/<name>.py`. Implement `measure(ir)` returning a `MetricResult`. Keep the implementation pure — no filesystem reads, no network calls; the IR is the only input.

**Step 6 — Ship the PROOF declaration.** Module-level `PROOF = ProofDeclaration(...)`:
- `pressure_claim` — the sentence from Step 3
- `pressure_runner(fixture) -> dict` — must include `{metric_name, cells, threshold, fires_at}` per `metric_proof.py`'s required fields
- `datum_name` — short, snake_case identifier
- `datum_runner(fixture) -> list[dict]` — one dict per datum instance, with `evidence` citing the cell_readings that drove it
- `corrective_runner(fixture, event) -> dict` — before/after shift when a cell is marked intentionally-excluded
- `code_tests_module` — dotted path
- `skill_test_fixture` — path to the IR fixture

Also add `DEFAULT_CORRECTION_EVENT` at module level.

**Step 7 — Build the IR fixture.** `s3/cubes/skill_tests/fixtures/<name>_metric_mini/fixture.py` — a Python module constructing a minimal `KnowledgeIR` with a cube + placements chosen so the metric fires with ≥1 datum instance. Commit the fixture builder, not a serialized IR (the IR has mutable context fields).

**Step 8 — Write the test module.** `s3/cubes/metrics/tests/<name>_test.py` with `run()` (exercises `measure` + datum runner against fixture) + `run_skill_test(fixture_path)` (reload + rerun).

**Step 9 — Semantic-balance check.** Estimate: on a representative IR, how many cells would your metric's datum_runner fire on? Call `balance_check(ir, projected_fires)`. If the metric would fire on >N× median, flag the concentration and ask before committing.

**Step 10 — Register + verify.** Add to `.claude/skills/_manifest.yaml` as `proof_status: ungated`. Wire into `run_proofs.py` via `run_metric_proofs` (or equivalent). Run; all four proofs must pass.

**Step 11 — Flip `proof_status: green`.** Add `proof_witness` + `authored_by` + `target_gap` (what reveal-gap this closed).

**Step 12 — Emit the network-extension report.** Build pre/post `CubeContext`; call `network_extension_report`. The *volume added* is not a source-region (metrics don't bring candidates) — it's a **reading-region**: the subset of cube state this metric now makes nameable. The *connected_to* should name the existing volumes whose cells this metric reads. Write to `.cube/reports/network/network_extension_<name>.md`.

### Piece 3 — Harness to install (mostly on disk)

- `s3/cubes/metrics/base.py` — MetricPlugin Protocol + MetricResult + MetricRegistry.
- `s3/cubes/proofs/metric_proof.py` — `verify_metric(module, fixture, correction_event)`.
- `s3/cubes/run_proofs.py` — orchestrates adapter + metric proofs; extend with `run_sweep_proofs` / `run_observation_proofs` as new module kinds author in.
- `s3/cubes/skill_support.py` — contextual-skill helpers.
- `s3/cubes/skill_tests/fixtures/` — fixture builders.
- `s3/cubes/metrics/tests/` — test modules (this directory is created on first metric authored).

### Piece 4 — Reference metric: vacuum

The `VacuumMetric` in `s3/cubes/metrics/vacuum.py` is the lowest reference. It reveals empty cells per rank; its datum is `vacuum_cell` (one instance per empty cell, with rank + coordinates + severity). Vacuum is to `metric-design` what Obsidian is to `adapter-design` — the smallest complete reference.

## The self-extension pattern

A metric's "service library" equivalent is the set of small **readings** — pure functions over IR state. Examples:
- `readings.per_rank_presence(ir) -> dict[int, set[str]]`
- `readings.load_distribution(ir) -> dict[str, int]`
- `readings.outbound_ref_graph(ir) -> dict[str, set[str]]`

If a metric needs a reading that doesn't exist, author it under `s3/cubes/metrics/readings/<name>.py` with the same shape as `s3/cubes/adapters/services/` (pure, typed, `READING` metadata dataclass, `run_self_test`). Register in `readings/__init__.py::REGISTRY`. The same **no speculative readings** rule applies: every reading authored must be consumed by the metric authored in the same run.

## Refusal rule

> *"I can describe a proposed metric, but I cannot register it until it ships four proofs (pressure / data-derivable datum / corrective hook / dual test) AND emits a network-extension report AND passes a semantic-balance check. A metric that duplicates an existing reveal is refused. A metric that fires on every cell (or none) is imbalanced."*

## Anti-patterns (refused on sight)

- **Duplicating an existing metric's cell_readings pattern** — extend the existing one, don't author alongside.
- **External-system vocabulary in pressure claim** — *"this metric counts tickets"* → refused; *"this metric surfaces ticket→cell orphans"* → accepted.
- **Metric that fires on every cell** — no balance. Split by rank or by predicate.
- **Metric with impure `measure(ir)`** — filesystem reads, network calls. Refused.
- **Vibed datums** — datum_runner that returns hand-authored strings without cell_readings citation.
- **Skipping Step 2 (diff against existing)** — metric collides with existing; authorship must amend, not duplicate.
- **Green manifest flip without wiring `run_metric_proofs`** — the metric must run through the proof harness, not just work standalone.
