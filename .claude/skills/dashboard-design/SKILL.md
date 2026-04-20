---
name: dashboard-design
description: Use this skill when the user wants the LLM to author a new Coverage Cube dashboard panel — a module that renders cube state + datum instances + metric readings + network-of-volumes structure into a human-legible artifact (markdown / HTML / ASCII / terminal / PNG). This skill is generative, contextual, and bound to the contextual-skill pattern (create-datum + semantic-balance obligations, four-piece protocol). Dashboard panels are *reveal-to-human* modules — they take structural cube state and project it onto a surface a user (or reviewer) can read directly. Invoke when the user says "add a dashboard panel", "render <X> as a view", "show me <Y> visually", "author a report panel for <Z>", "build a coverage view". Do NOT invoke for metric authoring — that is `metric-design`. Do NOT invoke for runtime display commands — those are `cube` (e.g. `cube coverage`). Keywords: dashboard design, dashboard panel, reveal-to-human, coverage view, report rendering, ASCII cube, rank bars, datum report, network visualization.
---

# Dashboard-Design Skill — Contextual, Generative, Reveal-to-Human

A module-authoring skill under the contextual-skill pattern. Authors a new dashboard panel as a **contextual move on the cube** — read current state, render a projection a human can read without decoding internal structure, ship four proofs + network-extension report + balance check.

| Skill | Answers |
|---|---|
| `cube` | Run existing dashboards (`coverage`, `vacuums`, `datums`, etc.). |
| `dashboard-design` | **Author a new reveal-to-human panel.** |
| `metric-design` | Compute a new measurement (numbers, not views). |
| `knowledge-shape` | Transform cube knowledge into external representations with preservation guarantees (planned). |

## Where dashboards sit (reveal-to-human)

Metrics produce `MetricResult` — numbers + structured cell_readings. Datums produce typed claims with evidence. Dashboards **compose** those into human-legible artifacts: markdown tables, ASCII cubes, rank bars, network diagrams, coverage maps, top-N datum lists with citation links.

Reference panels already on disk (as building blocks, not yet module-ized):
- `dashboard.py::render_ascii_cube` — 3-cube with `[X]` placed / `[ ]` empty
- `dashboard.py::render_rank_bars` — horizontal bar graphs per rank
- Datum-first report — top datums + backdrop coverage

## The two obligations

1. **create-datum** — the panel must surface at least one datum or metric reading whose rendering makes a claim the reader can act on. Pretty pictures without actionable claims are refused.
2. **semantic-balance** — the panel must render proportionately across cube state. A panel that gives one region 80% of its real-estate while ignoring the rest is imbalanced; either split or flag.

## The four framed pieces

### Piece 1 — Requirements for the LLM (the contract)

- **Protocol** (to be added to `s3/cubes/dashboards/base.py` when first panel authored under this skill lands):
  ```python
  class DashboardPanel(Protocol):
      name: str
      output_kind: str  # "markdown" | "ascii" | "html" | "terminal" | "png"
      def render(self, ir: KnowledgeIR, metrics: list[MetricResult],
                 datums: list[DatumInstance]) -> RenderResult: ...
  ```
- **`RenderResult`**: `name`, `output_kind`, `body` (string/bytes), `citations` (list of cell / source / datum ids the render cites), `summary` (one-line).
- **Pure render**: no I/O to external services. Output goes through the caller; the panel returns bytes/string.
- **PROOF**: module-level `ProofDeclaration` — pressure_claim names what audience gap the panel fills; datum_runner emits one or more `panel_render_datum` instances citing what was surfaced; corrective_runner shows measurable shift when a datum is marked `suppressed_from_panel`.
- **Test module**: `run()` asserts render output shape + citation correctness.
- **Fixture**: small IR + metric + datum set; canonical expected render snippet (golden-test style).

### Piece 2 — Generative engine (contextual authorship flow)

**Step 0 — Identify the audience + gap.** Who reads this panel (architect / reviewer / LLM / CI log)? What current panel leaves this audience guessing?

**Step 1 — Read cube context.** Shape the panel around current state — if the cube is mostly vacuum, the panel's top-line should lead with vacuums; if it's placement-dense, lead with coverage.

**Step 2 — Diff against existing panels.** `dashboard.py` has coverage, rank bars, ASCII cube, datum list. Confirm the new panel is distinct in audience-gap, not a re-render.

**Step 3 — Pick `output_kind`.** `markdown` is the default (witness artifacts). `ascii` for CLI. `html` for richer rendering. `png` requires PIL — declare the dep explicitly.

**Step 4 — Author the panel module.** `s3/cubes/dashboards/<name>.py`. Implement `render`. Pure. Inputs: IR + metrics + datums. Outputs: RenderResult with citations.

**Step 5 — Ship PROOF.** Same four runners. Datum runner emits `panel_render_datum` per major section rendered. Corrective runner shows suppressed datums disappearing.

**Step 6 — Build the render fixture.** Small IR + 2-3 metric results + 3-5 datum instances. Golden snippet for expected output.

**Step 7 — Write the test module.** Assert render body contains expected sections + citations resolve to fixture ids.

**Step 8 — Semantic-balance check.** On a real IR, how much of the rendered output is devoted to one cell / one rank? Flag if >N% concentrated.

**Step 9 — Register + verify.** Add to `.claude/skills/_manifest.yaml` as `proof_status: ungated`. Wire a `run_dashboard_proofs` into `run_proofs.py` (first panel pays this cost).

**Step 10 — Flip `proof_status: green`.**

**Step 11 — Emit network-extension report.** Volume added = a **rendering-region**. Connected to adapter volumes + metric volumes whose state the panel surfaces.

### Piece 3 — Harness (mostly to be wired when first panel lands)

- `s3/cubes/dashboards/base.py` (first panel authors alongside).
- `s3/cubes/proofs/dashboard_proof.py` (follow `metric_proof.py` shape).
- `s3/cubes/run_proofs.py` — needs `run_dashboard_proofs`.
- `s3/cubes/skill_support.py` — already ships helpers.

### Piece 4 — Reference panels (building blocks)

- `dashboard.py::render_ascii_cube` — reference for `output_kind: ascii`
- `dashboard.py::render_rank_bars` — reference for markdown rank bars
- `.cube/reports/` output artifacts — reference for markdown datum-first report

## Self-extension pattern

Panels may need rendering helpers: markdown table builders, ASCII line-drawing, color-code mappers. Author under `s3/cubes/dashboards/renderers/<name>.py` with the same contract as services. No speculative renderers.

## Refusal rule

> *"I can describe a proposed panel, but I cannot register it until it ships four proofs AND cites specific cells / datums / metrics in its render AND passes a semantic-balance check. A panel that renders without citations is decoration — refused."*

## Anti-patterns (refused on sight)

- **Decoration-without-citation** — pretty but not actionable; citations field must list real ids.
- **One-region dominance** — panel gives 80% of its area to one cell while ignoring the rest; refused unless user explicitly confirms the focus.
- **I/O side effects** — render is pure; caller handles writing output.
- **Duplicates an existing panel** — extend or compose; don't re-render.
- **Over-dense render** — if the panel output exceeds N screen-fulls, split into linked sub-panels.
- **Silent suppression** — if corrective whitelist suppresses datums from the render, the panel must surface the suppression count.
