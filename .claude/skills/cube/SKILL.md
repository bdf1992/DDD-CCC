---
name: cube
description: Use this skill when the user asks for semantic coverage measurement, a test-pyramid-style map of a repo (unit / integration / interface / e2e / smoke / regression / mutation), placement of code or documents onto a structured substrate, or wants to see what's "empty" (vacuums) or "in tension" (frustrated) in their codebase. Also invoke when the user asks to ingest a repo into a cube, run an initial orientation sweep, suggest placements for code artifacts, or emit Greenfield-shape datapoints from placement decisions. Use it for static-analysis-shape questions (lint / type / SAST admissibility at the stalk level), branch / line / function coverage reads, contract or interface testing, mutation testing (blind-cell detection via perturbation), shift-left timing (ide/commit/ci/post-deploy), and ecosystem-scale coverage across multiple complexes. Keywords that trigger this skill: cube, substrate, coverage map, vacuum, frustration, placement, semantic test, combinatorial complex, element cube, orientation sweep, datapoint stream, unit test, integration test, interface test, contract test, e2e test, smoke test, regression test, mutation test, branch coverage, line coverage, static analysis, SAST, shift-left.
---

# Coverage Cube — Semantic Coverage Substrate

**Formal**: a pluggable dynamical measurement substrate over a combinatorial complex, using invariant-axis projections to place heterogeneous knowledge sources into semantic coverage, vacuum, and tension fields.

**Product**: drops into any repo, measures what's covered / what's empty / what's in tension, and emits a signed audit trail the user (or an LLM) can read as a semantic test pyramid.

**The cube is machinery; the datums it produces are the product.** A Rubik's cube is only interesting because its state licenses actions. Same here. The user-facing output is a stream of typed, cited, actionable datums: *"docs at section X are 42 days older than the code they reference,"* *"this region is 80% prose and 5% prototype,"* *"these terms appear in the corpus but bind to no cell,"* *"this edge is frustrated — unit tests pass but the integration would fail."* The cube is how those datums become computable.

**Role**: this is the *first sensorium* — the measurement surface every later tool is judged against. Not the whole platform.

**The doctrines it serves**:

- **The Datum-Preserving Knowledge Loop.** Generative systems can create and transform project knowledge faster than humans can verify whether meaning, evidence, structure, and actionability survived. Coverage Cube is the accountability layer: `external knowledge → SourceRecord → CandidateStore → placement → measurement → datum → KnowledgeIR → shaped output + preservation report`. The goal is *preserving actionable meaning across representation change*, not preserving the cube itself.
- **The Eval Pressure Loop (Human-Anchored).** Humans define the success surface (which data matters, what form it must take, what evidence is admissible). The system generates into *measured absences* — work vacuums, eval vacuums, citation vacuums, representation vacuums. Cube slots are an external attention scaffold; datums are the admissible unit of claim.
- **The Bootstrap Instantiation Protocol.** Coverage Cube is not installed as a generic tool — it is *instantiated per project*. A single pasteable bootstrap-skill markdown file inspects a foreign repo, derives Profile Card + axes from the repo's own goals and decomposition, asks permission, installs a pinned `.regencies/` skill pack, and produces a first semantic-coverage report. Boring, permissioned, reversible. Instructions + reports only on day zero; executable automation later. The cube is the *latent upgrade path*, not the day-zero dependency.
- **The Progressive Discovery Doctrine.** The cube never concludes. Every chunk ingested, every metric read, every datum firing is a *refinement event* tightening priors — not a verdict. Profile Card, axis convention, datum relevance, vocabulary all *evolve*. Chunked ETL + observations are the mechanical foundation; the signed datapoint chain is the learning trajectory. Refuse to present output as conclusive; every instance carries a timestamp and run fingerprint. Complementary to Doctrine 2: pressure-side vs refinement-side.
  - **Operational mode — chunked bidirectional discovery.** Progressive discovery is how the LLM + cube + user interact. Chunks of loop state are small enough to not overwhelm either party, large enough to carry signal. Two first-class chunk types: **anchor points** (user-accepted placements — expansion licenses; propose larger similar batches) and **correction points** (user-rejected/modified placements — caution priors; pull back to small careful chunks in that region). Chunk grain is adaptive: small at the frontier, larger around anchors, small again around corrections. `cube accept` = anchor, `cube reject`/`modify` = correction; the signed chain is the accumulated anchor+correction map.
- **The Module-Skill Composition + Proof Discipline.** The cube is not one skill — it is a library of **module-authoring skills** (`adapter-design`, `metric-design`, `datum-design`, `sweep-design`, `observation-design`, `transducer-design`, `dashboard-design`) plus one workflow skill (`cube`), composed by a declarative `_manifest.yaml`. Every module-skill ships **four proofs** or it does not ship: (1) a *pressure claim* loggable against specific cells / datums; (2) a *data-derivable datum* computed from inputs, never hand-authored prose; (3) a *corrective pattern hook* so user rejections visibly shift subsequent output; (4) a *dual test* — code TDD plus a skill-vs-code agreement test that follows the authorship protocol end-to-end and verifies the authored module integrates. Refuse to ship a module-skill as documentation; refuse to accept vibed datums; refuse to load modules outside the manifest.
  - **Contextual-skill pattern.** Authorship skills are **contextual moves on the cube**, not static input→output functions. Every invocation must fulfill two obligations: **create-datum** (produce at least one typed, cited datum instance) + **semantic-balance** (leave the cube more balanced or surface imbalance). Implemented as a four-piece pattern: (1) **intent-as-pressure** — skill names what pressure it creates/reveals; (2) **context-before-propose** — skill reads cube state (`s3/cubes/skill_support.py::read_cube_context`) before generating; (3) **datum-first, network-extension output** — every run ships `(artifact, datum_instances, network_extension_report)`, never just the artifact; (4) **semantic-balance check** — project load impact, refuse silent concentration. Refuse skills that echo-to-fixed-point; require growing a **network of volumes** (3-cells connected by shared faces / edges / vertices) across runs. Workflow skills (`cube`) are exempt — they operate, they do not author.

Source lives under `s3/cubes/`.

## The mental model

- **Cube is machinery; datums are the product.** The user-facing output is a stream of typed, cited, actionable signals. The cube makes those signals computable. Metrics are raw reads of cube state; **datums** compose metrics + adapter content to surface meaning (staleness, composition ratios, vocabulary gaps, structural frustrations). Users register their own datums; the library ships a default catalog.
- **Retrieval is contextual, not flat.** Contextual RAG = `(content similarity × cell locality × relation type)`. The cell complex supplies spatial / structural locality that flat vector search can't produce. *"Find what's near `f2-0` semantically AND structurally"* has a well-defined answer here.
- **Cell rank = test scale.** 0-cell (vertex) = unit. 1-cell (edge) = integration. 2-cell (face) = interface. 3-cell (volume) = e2e. Rank ≥ 4 (hypergraph between complexes) = ecosystem / multi-system.
- **Sub-unit slot** for static analysis / linting / type checks / SAST: stalk-admissibility predicate *below* rank 0 — content must pass local axioms before it can occupy a cell at all.
- **Smoke** = Cantor-dust fractal measure on cells of any chosen rank (cheap breadth, continuous density knob).
- **Regression** = a pinned subset of cells that must re-verify every sweep (monotone grow-only).
- **Mutation testing** = perturb a cell's content + check if any metric plugin responds. If none do, that region is blind to your measurement suite.
- **Branch coverage** = rank-1 edge-presence specifically for the pair of edges out of a branching vertex (falls out of edge coverage).
- **Line / function / branch coverage maps** = the dashboard render of cell-presence at the appropriate rank.
- **Shift-left / CI timing** = each measurement plugin declares `fires_at` ∈ {`ide`, `commit`, `ci`, `post-deploy`}.
- **Coverage beyond presence.** Vacuum (empty cell) = untested territory. Frustrated sheaf H⁰ > 0 on an edge = unit tests pass but integration would fail, surfaced before someone writes the integration test.
- **Cube is substrate.** The user declares what axes mean; we run load, measure, and read.
- **Datapoint stream is Greenfield-shape.** Every placement, every accept/reject, every NL reasoning gets emitted as a signed hash-chained record.

## When to invoke

Invoke this skill when the user:
- Asks to map / measure / cover / audit a codebase or repo
- Wants to surface specific datums like: "is our documentation stale vs the code?", "how much of this region is prose vs prototype?", "what terms appear but aren't mapped?", "where are the structural tensions?"
- Wants a test-pyramid-shape report on something other than runnable tests
- Says "cube", "substrate", "vacuum", "frustration", "coverage map", "element cube", "orientation sweep", "datum", "contextual rag"
- Asks for placement suggestions for code, docs, ideas, or datapoints
- Wants to apply semantic coverage measurement to their own repo

Do **not** invoke when the user is asking about runnable unit/integration tests in the traditional sense — that's `pytest`. This skill is for semantic coverage, not behavioral assertion.

**Sibling skills** form a library of module-authoring skills plus one workflow skill. Route based on the user's intent:

**Workflow skill** (operate the substrate):
- *"Run / measure / show / ingest / audit"* → `cube` skill (this one).

**Module-authoring skills** (extend the substrate — each ships the four proofs before it counts):
- *"Author a new source adapter (Obsidian, Postgres, JIRA, Drive, etc.)"* → `adapter-design` (`.claude/skills/adapter-design/SKILL.md`).
- *"Author a new metric plugin (coverage / vacuum / frustration / custom)"* → `metric-design`.
- *"Author a new datum type — an actionable signal derived from data"* → `datum-design` (`.claude/skills/datum-design/SKILL.md`).
- *"Author a new orbit-integrated sweep"* → `sweep-design`.
- *"Author a new chunked-ETL observer"* → `observation-design`.
- *"Author a new Knowledge Shape transducer (cube → external representation)"* → `transducer-design` (stub).
- *"Author a new dashboard panel / report"* → `dashboard-design`.

If the user has an idea for a new actionable signal specific to their project's storage patterns, interaction patterns, or semantic structure, it's a `datum-design` job.

Every module-authoring skill rejects shipping without its four proofs (pressure / data-derivable datum / corrective hook / dual test). When the user asks to author a new module, surface the proof obligations *before* writing code.

## Commands

All commands are Python scripts under `s3/cubes/`. Run from the repo root:

```bash
# Source adapters + store + base measurement spine
python s3/cubes/cli.py sources list
python s3/cubes/cli.py sources add markdown ./docs
python s3/cubes/cli.py sources add obsidian ./vault
python s3/cubes/cli.py sources add greenfield-jsonl ./greenfield/data
python s3/cubes/cli.py ingest                   # run all configured adapters → candidates
python s3/cubes/cli.py suggest [<candidate_id>] # top-N cells with predictive scores
python s3/cubes/cli.py accept <candidate_id> <cell_id> --reason "..."
python s3/cubes/cli.py reject <candidate_id> <cell_id> --reason "..."
python s3/cubes/cli.py modify <candidate_id> <new_cell_id> --reason "..."
python s3/cubes/cli.py coverage                 # rank-colored presence map
python s3/cubes/cli.py vacuums                  # empty cells by rank
python s3/cubes/cli.py frustrations             # H⁰-disagreement edges
python s3/cubes/cli.py datums                   # the user-facing product: top-N typed, cited datums
python s3/cubes/cli.py datums --family staleness
python s3/cubes/cli.py datums --family composition
python s3/cubes/cli.py datums --family vocabulary
python s3/cubes/cli.py rag <query> [--anchor <cell_id>]  # contextual RAG query
```

Witness output lands under `.cube/reports/`.

## The interview loop

When the user wants to walk a coverage session:

1. Run `cli.py ingest <repo_path>` — builds candidate pool.
2. For each candidate (or a sampled subset), run `cli.py suggest <id>` — library proposes top-N cells with predictive scores (coverage delta, frustration delta, vacuum delta).
3. Present the suggestion to the user with the predictive terms.
4. User says yes / no / "try a different cell" / provides natural-language reasoning.
5. You translate NL reasoning into the structured fields and call `cli.py accept / reject / modify`.
6. After a batch, run `cli.py show coverage` and discuss vacuums + frustrations with the user.

## Conventions

- Constants come from `primitives.py` (`V`, `FANO`, `Bott`, `S_V`, etc.). Never hardcode.
- **Ports-and-adapters invariant.** A source adapter *never* writes directly to the cube. The only path is `Adapter → CandidateStore → PlacementEngine → Decision → Datapoint`. Stores are retrieval / cache / index — **not** the truth model. The truth model is the signed datapoint stream + cube placement history.
- **Markdown / Obsidian / JIRA / DB / vector docs are not special.** Each is a `SourceAdapter` that emits the same canonical `SourceRecord`. After normalization they're all comparable as candidates.
- Placement commits are atomic and produce a signed datapoint; the stream is the audit trail.
- The element cube is the first registered cube type. Other cube types plug in later without rewriting the spine.
- Orientation-orbit sweep runs once at ingest; per-frame signals expose anisotropy, orbit-integrated signals are the baseline.

## References

- Constants: `primitives.py`
- Cube core: `s3/cubes/combinatorial_complex.py`, `s3/cubes/element_cube.py`
- Manifest: `.claude/skills/_manifest.yaml`
