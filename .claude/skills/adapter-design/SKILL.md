---
name: adapter-design
description: Use this skill when the user wants the LLM to author a new Coverage Cube SourceAdapter by reading the target repo, reading the cube's current state, and composing from the pluginable services library. This skill is generative, self-extending, and *contextual* — it inspects the repo + the cube, inventories source systems, picks adapter targets informed by existing vacuums and anchor density, reuses or authors services as needed, writes the adapter, writes a repo-derived fixture, writes the test module, ships all four proofs (pressure / data-derivable datum / corrective hook / dual test), AND emits a network-extension report + semantic-balance check per run. Invoke when the user says "author an adapter for this repo", "add a new adapter", "write an adapter for <X>", "ingest <Y> into the cube", "teach the cube to read this", "bootstrap the adapter layer". Do NOT invoke when the user wants to operate an existing adapter — that is `cube`. Keywords: adapter design, source adapter, SourceAdapter, SourceRecord, adapter authoring, adapter proof, self-extending skill, pluginable services, generative adapter, contextual skill, network extension, repo-read, ingest new source.
---

# Adapter-Design Skill — Contextual, Generative, Self-Extending

A module-authoring skill under the contextual-skill pattern. It authors a new adapter as a **contextual move on the cube** — not a static function that returns a module. Every run reads the cube's current state first, produces an adapter *and* a datum instance *and* a network-extension report, and passes a semantic-balance check before committing.

| Skill | Answers |
|---|---|
| `cube` | Run / measure / ingest / audit existing adapters. |
| `adapter-design` | **Author a new adapter for this repo as a contextual cube-move.** |
| `datum-design` | Define a new actionable signal derived from data. |
| `metric-design` | Define a new measurement over cube state. |
| `knowledge-shape` | Transform cube knowledge into a different representation. |

## The two obligations

Every invocation of this skill **must** fulfill both obligations or refuse to ship:

1. **create-datum** — the run produces at least one typed, cited, actionable datum instance derived from the target repo's data. Not "here's your adapter." *"Here's the adapter + this specific datum it lets the cube compute + the evidence."*

2. **semantic-balance** — the run leaves the cube more balanced (or surfaces imbalance for the user). If the authored adapter would concentrate load on one cell while starving others, the skill flags that and asks before committing.

Skills that echo-to-fixed-point (produce an adapter without a datum + without a balance check) are refused at this skill's output gate.

## The four framed pieces

### Piece 1 — Requirements for the LLM (the contract)

The adapter the LLM writes must satisfy:

- **Protocol**: `s3/cubes/adapters/base.py::SourceAdapter` — `name: str`, `discover()`, `read()`, `changed_since()`.
- **Output shape**: every candidate emitted as `SourceRecord` with all required fields set.
- **Ports-and-adapters invariant**: never writes to the cube directly. Emits candidates only; placement decides.
- **Metadata preservation**: verbatim pass-through; no interpretation.
- **PROOF**: module-level `PROOF: ProofDeclaration` + `DEFAULT_CORRECTION_EVENT` dict.
- **Test module**: `run() -> dict` + `run_skill_test(fixture_path) -> dict`.
- **Fixture**: carved from the target repo itself; minimal; committed.
- **Intent-as-pressure**: the pressure the adapter creates/reveals is nameable in cell/candidate/datum language, not external-system language.

### Piece 2 — Generative engine (contextual authorship flow)

Each step produces a named artifact. Steps are not optional; skipping any step invalidates the authorship.

**Step 0 — Read the target repo.** Walk the directory tree. List extensions. Find config files / schemas / dotfiles that indicate source systems. Read one sample per candidate source-system to understand structure + metadata. This is the *target-reading* move.

**Step 1 — Read cube context.** *This is the distinguishing contextual move.* Call `s3.cubes.skill_support.read_cube_context(ir)` on the current cube IR. Capture:
- Placed cells + load per cell
- Vacuum cells by rank
- Recent provenance count (anchor + correction density proxy)
- Axis convention

The output is a `CubeContext` object. The adapter you author must be shaped by this context — e.g. if the cube already has an adapter covering 60% of the candidate cells this adapter would target, split the scope rather than duplicate.

**Step 2 — Inventory source systems.** One short list: each entry = one source system + one-sentence description + count of candidate units. If two candidates overlap, pick the more specific one.

**Step 3 — Pick adapter targets.** Author one adapter per source system the user wants ingested. Do not author for systems out of scope. Cross-reference Step 1: if a target's cells are already well-placed, propose a narrower scope or defer.

**Step 4 — Audit services + propose composition.** Call `s3.cubes.adapters.services.audit_library()`. Halt on any red service. List the small operations the adapter needs; match each to an existing service.

**Step 5 — Compose or extend services.** For operations the library covers, import. For operations it doesn't, author a new service module under `s3/cubes/adapters/services/<name>.py` per `services/README.md` (pure, typed, `SERVICE` declaration, `run_self_test`). Add to `REGISTRY`. Re-run `audit_library()` — must pass.

**Step 6 — Author the adapter.** `s3/cubes/adapters/<name>.py`. Imports from services. Implements Protocol. Declares `PROOF` + `DEFAULT_CORRECTION_EVENT` at module level. Ships pressure / datum / corrective runners.

**Step 7 — Carve the fixture.** Copy a small real subset of the target repo into `s3/cubes/skill_tests/fixtures/<name>_mini/`. Large enough to fire the pressure claim + produce ≥1 datum instance. Small enough to commit. README documents expected counts.

**Step 8 — Write the test module.** `s3/cubes/adapters/tests/<name>_test.py` with `run()` + `run_skill_test(fixture_path)`.

**Step 9 — Semantic-balance check.** *This is the second distinguishing contextual move.* Estimate candidate count × target cell distribution for the adapter running against the real target repo (not the fixture). Call `s3.cubes.skill_support.balance_check(ir, projected)`. If `balanced=False`, **stop** and surface the imbalance + the suggested split to the user. Do not commit to manifest until either the user approves or the scope is split.

**Step 10 — Register + verify.** Add the adapter to `.claude/skills/_manifest.yaml` as `proof_status: ungated`. Run `python -m s3.cubes.run_proofs`. All four proofs must pass.

**Step 11 — Flip `proof_status: green`.** Add `proof_witness` + `authored_by` + `target_repo`. Signed revision event emitted.

**Step 12 — Emit the network-extension report.** *This is the third distinguishing contextual move.* Build a post-run `CubeContext` and call `s3.cubes.skill_support.network_extension_report(pre_ctx, post_ctx, module_name, volume_added, connected_to, datum_names, vacuums_filled, vacuums_revealed)`. Render via `render_report_markdown()` and write to `.cube/reports/network/network_extension_<name>.md`. Without this artifact, the run is incomplete.

### Piece 3 — Harness to install (already on disk)

- `s3/cubes/manifest.py` — loads, validates, diffs, signs revisions.
- `s3/cubes/proofs/` — `verify_adapter` + the three per-kind runners.
- `s3/cubes/run_proofs.py` — runs the harness against every manifest-declared adapter (honors `init_kwargs`, reads `DEFAULT_CORRECTION_EVENT`).
- `s3/cubes/adapters/services/` — growing services library with `audit_library()`.
- `s3/cubes/adapters/tests/` — test modules.
- `s3/cubes/skill_tests/fixtures/` — carved fixtures.
- `s3/cubes/skill_support.py` — **contextual-skill helpers**: `read_cube_context`, `balance_check`, `network_extension_report`, `render_report_markdown`. These are the Piece 2/3/4 primitives.

### Piece 4 — Reference adapters on disk

**Obsidian — the lowest reference**. Small, bounded unit; clear unresolved-wikilink pressure.

| Artifact | File |
|---|---|
| Adapter | [`s3/cubes/adapters/obsidian_vault.py`](../../../s3/cubes/adapters/obsidian_vault.py) |
| Test | [`s3/cubes/adapters/tests/obsidian_vault_test.py`](../../../s3/cubes/adapters/tests/obsidian_vault_test.py) |
| Fixture | [`s3/cubes/skill_tests/fixtures/obsidian_vault_mini/`](../../../s3/cubes/skill_tests/fixtures/obsidian_vault_mini/) |
| Witness | `.cube/reports/proofs_summary.json` |

**CSharpUnity — the first non-seeded reference**. Demonstrates the services library growing on-demand (1 → 3 services in one run).

| Artifact | File |
|---|---|
| Adapter | [`s3/cubes/adapters/csharp_unity.py`](../../../s3/cubes/adapters/csharp_unity.py) |
| Services authored in this run | [`csharp_usings.py`](../../../s3/cubes/adapters/services/csharp_usings.py), [`csharp_namespace.py`](../../../s3/cubes/adapters/services/csharp_namespace.py) |
| Test | [`s3/cubes/adapters/tests/csharp_unity_test.py`](../../../s3/cubes/adapters/tests/csharp_unity_test.py) |
| Fixture | [`s3/cubes/skill_tests/fixtures/csharp_unity_mini/`](../../../s3/cubes/skill_tests/fixtures/csharp_unity_mini/) |
| Network-extension report | `.cube/reports/network/network_extension_csharp_unity.md` |

## The self-extension pattern

When the target surfaces a source-system operation the library doesn't cover, the skill **authors a new service module** under `services/<name>.py` in the same run, composes it into the adapter, and registers it in `REGISTRY`. No speculative services — every service authored must be consumed by the adapter authored in the same run. Bricks, not migrations; a near-miss gets an adjacent service, not an in-place refactor.

## The configure-self move

At Step 1, the skill diffs:

- **Capability inventory** — what the services library + existing adapters can already express
- **Target inventory** — what source systems the target repo contains
- **Cube-state inventory** — which cells are already populated, which vacuums exist

For each target source-system, the skill decides: *reuse existing adapter* / *extend a service* / *author new service(s) + adapter*. The decision log writes to `.cube/reports/run_log_<name>.md` — auditable, diff-able across runs.

## Refusal rule

> *"I can describe a proposed adapter, but I cannot register it until it ships four proofs (pressure / data-derivable datum / corrective hook / dual test) AND emits a network-extension report AND passes a semantic-balance check. The adapter without the report is incomplete. The adapter that concentrates load without asking is imbalanced."*

An adapter is not shipped until:
1. `run_proofs.py` prints `[OK] adapters/<name>: 4/4 proofs`
2. `balance_check` returns `balanced=True` (or user explicitly approves the imbalance)
3. `network_extension_report` written under `.cube/reports/network/`
4. Manifest flip commits signed revision event

## Anti-patterns (refused on sight)

- **Echo-to-fixed-point** — returning an adapter without a datum instance, a network-extension report, and a balance check.
- **Vibe-authoring** — writing an adapter without reading the target repo AND the cube state.
- **Synthetic fixture** — fixtures not carved from the real target repo. Proofs that don't bind to reality.
- **Orphan service** — a service authored with no consumer in the same run. Speculative services rot.
- **Skipped `audit_library`** — building on a red foundation.
- **Overlapping adapters in one run** — pick the more specific; the other is a separate run.
- **Silent concentration** — committing an adapter whose candidate distribution would overwhelm one cell, without surfacing and asking.
- **Green manifest flip without proof witness** — `proof_status: green` requires `proof_witness` pointer, and `network_extension_<name>.md` + (optional) `run_log_<name>.md` under `.cube/reports/`.
- **Refactoring an existing service for a new variant** — brick, not migration. Author alongside.
