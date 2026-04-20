---
name: observation-design
description: Use this skill when the user wants the LLM to author a new Coverage Cube chunked-ETL observer — a plugin that consumes the candidate chunk stream during ingest and maintains running statistics / priors (vocabulary accumulators, axis-entropy trackers, datum-prior counters, vocabulary vacuum detectors, etc.). This skill is generative, contextual, and bound to the contextual-skill pattern (create-datum + semantic-balance obligations, four-piece protocol). Observers are *progressive-discovery* modules — they turn incremental ingest into refinement priors per Doctrine 4. Invoke when the user says "add a new observer", "watch <X> during ingest", "accumulate <Y> across chunks", "track <Z> refinement", "author a chunked-ETL observer". Do NOT invoke for single-shot metrics — that is `metric-design`. Keywords: observation design, observer, chunked ETL, progressive discovery, refinement prior, running statistic, vocabulary accumulator, axis entropy tracker, datum prior, observer proof.
---

# Observation-Design Skill — Contextual, Generative, Progressive-Discovery

A module-authoring skill under the contextual-skill pattern. Authors a new chunked-ETL observer as a **contextual move on the cube** — read current state, consume the chunk stream as ingest runs, accumulate running statistics that tighten priors across chunks, ship four proofs + network-extension report + balance check.

| Skill | Answers |
|---|---|
| `cube` | Run / ingest / display observers' accumulated state. |
| `adapter-design` | Bring new source material onto the substrate (one-shot discovery). |
| `metric-design` | Compute a measurement over full IR state (one-shot reveal). |
| `observation-design` | **Watch the chunk stream during ingest and refine priors over time.** |
| `datum-design` | Define a typed claim derived from signals. |

## Where observers sit (progressive discovery)

Adapters and metrics are **one-shot**: an adapter reads a source tree once, a metric reads IR state once. Observers are **incremental**: they consume candidates in chunks during ingest, maintain running statistics, and emit refinement events as chunks land.

Reference purposes (Progressive Discovery's operational mode — chunked bidirectional discovery):

- **vocabulary_accumulator** — tracks terms appearing across candidates; reveals vocabulary vacuums (terms in the corpus but bound to no cell)
- **axis_entropy_tracker** — tracks distribution of candidate field values; reveals when a new axis candidate has high entropy relative to committed axes
- **datum_prior_tracker** — tracks which datum types fire and at what rate; adjusts thresholds per datum as evidence accumulates
- **anchor_correction_density_tracker** — tracks recent accept vs reject rate near each cell; feeds chunk-grain adaptation

## The two obligations

1. **create-datum** — each ingest chunk must produce at least one typed refinement-event datum if state changed, or explicit `no_change` if it didn't. The observer is not allowed to silently accumulate.
2. **semantic-balance** — the observer must fire on a balanced subset of chunks. Firing on every chunk is noise; firing on none is uninformative. Balance check projects chunk-distribution and flags over/under-fire.

## The four framed pieces

### Piece 1 — Requirements for the LLM (the contract)

- **Protocol** (to be added to `s3/cubes/observations/base.py` when first observer lands):
  ```python
  class ObserverPlugin(Protocol):
      name: str
      fires_at: frozenset[str]    # {"chunk", "ingest_start", "ingest_end"}
      def on_chunk(self, chunk: list[SourceRecord], ctx: ObserverContext) -> ObservationResult: ...
      def checkpoint(self) -> dict: ...
      def restore(self, state: dict) -> None: ...
  ```
- **`ObservationResult`**: `name`, `scalars`, `refinement_events`, `summary`.
- **Checkpointable**: the observer's internal state serializes so subsequent ingests continue from where the prior left off (chunk-monotonicity).
- **PROOF** at module level — same four proofs, with pressure_runner / datum_runner / corrective_runner / dual test.
- **Test module**: `run()` replays a canonical chunk stream and asserts running-state progression.
- **Fixture**: sequence of 3-5 chunks covering cold start / accumulation / refinement cases.

### Piece 2 — Generative engine (contextual authorship flow)

**Step 0 — Identify the refinement gap.** What aspect of the ingest chunk stream isn't currently being accumulated that should be? Name the gap in refinement-prior language.

**Step 1 — Read cube context.** `read_cube_context(ir)`. The observer's accumulation should be *shaped* by what's already in the cube — e.g., if one axis is dominant, the axis-entropy tracker's starting priors reflect that.

**Step 2 — Diff against existing observers.** Does a registered observer already accumulate this signal? If yes, extend its scalars; if no, author new.

**Step 3 — Pick `fires_at`.** `chunk` (every chunk), `ingest_start` (reset priors), `ingest_end` (emit final refinement datum). Narrowest meaningful set.

**Step 4 — Design the state machine.** What does the observer carry between chunks? Counters, rolling windows, exponential-moving averages, histograms, sets. Write the state dataclass first.

**Step 5 — Author the module.** `s3/cubes/observations/<name>.py`. Implement `on_chunk`, `checkpoint`, `restore`. Keep pure: inputs are chunk + context + prior state; output is new state + refinement events.

**Step 6 — Ship PROOF**. Pressure claim names what refinement-pressure the observer reveals. Datum runner emits one or more refinement-event datums per chunk. Corrective runner shows measurable shift when a chunk is marked `exclude_from_priors`.

**Step 7 — Build the chunk-stream fixture.** `s3/cubes/skill_tests/fixtures/<name>_observation_mini/fixture.py` — a Python module yielding a canonical 3-5 chunk sequence.

**Step 8 — Write the test module.** Replays the chunk stream; asserts state progression + refinement events.

**Step 9 — Semantic-balance check.** On a representative ingest stream, how often does this observer fire refinement events? Call `balance_check`. Flag over/under-fire.

**Step 10 — Register + verify.** Add to `.claude/skills/_manifest.yaml` as `proof_status: ungated`. Wire a `run_observer_proofs` into `run_proofs.py` (first observer pays this cost).

**Step 11 — Flip `proof_status: green`** with `proof_witness` + `authored_by` + `target_gap`.

**Step 12 — Emit network-extension report.** Volume added = a **refinement-region** (the subset of cube state this observer now tracks over time). Connected to existing volumes via the placement-set or axis-convention face.

### Piece 3 — Harness (mostly to be wired when first observer lands)

- `s3/cubes/observations/base.py` (not yet authored — first observer authors it alongside).
- `s3/cubes/proofs/observer_proof.py` (not yet authored — follow `metric_proof.py` shape).
- `s3/cubes/run_proofs.py` — needs `run_observer_proofs` added parallel to adapters + metrics.
- `s3/cubes/skill_support.py` — already ships context / balance / network helpers.

### Piece 4 — Reference observer

None yet; the first observer authored under this skill becomes the reference. Recommended first candidate: `vocabulary_accumulator` — smallest complete example (set + delta emission), clear pressure claim (terms bound to no cell), clear datum (`new_orphan_term`).

## Self-extension pattern

Observers may need small helpers: chunk filters, rolling-window data structures, exponential-decay accumulators. Author these under `s3/cubes/observations/helpers/<name>.py` with the same contract as `s3/cubes/adapters/services/`. No speculative helpers.

## Refusal rule

> *"I can describe a proposed observer, but I cannot register it until it ships four proofs AND emits refinement events per chunk AND passes a semantic-balance check. An observer that accumulates state without emitting refinement-event datums is silent — refused."*

## Anti-patterns (refused on sight)

- **Silent accumulation** — observer that only updates internal state without emitting refinement events.
- **Non-checkpointable state** — breaks chunk-monotonicity; refused.
- **Fires on every chunk unconditionally** — balance violation.
- **Duplicates an existing observer's accumulation** — extend, don't author alongside.
- **Side effects beyond state + events** — observers are pure over `(chunks, context, prior state)`.
- **Overwrites anchor / correction chain events** — observers read the chain for priors; they do not mutate it.
