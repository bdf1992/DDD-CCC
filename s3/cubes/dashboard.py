"""
Dashboard — renders a KnowledgeIR into human-readable markdown artifacts.

Two outputs, with the datum-first view as the product and coverage as backdrop:

    datums.md    — top-N datums with cell-grounded citations + actionable hints
                   + proposed gaps; reads as a semantic-coverage report a
                   person or LLM can act on directly
    coverage.md  — structural backdrop: coverage per rank, vacuum cells,
                   frustrated edges, richness, Profile Card summary

Nothing in the renderer introduces new measurement logic — it consumes
pre-computed MetricResults + DatumInstances + IR state.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from s3.cubes.ir.graph import KnowledgeIR
    from s3.cubes.metrics.base import MetricResult
    from s3.cubes.datums.base import DatumInstance
    from s3.cubes.profile.card import ProfileCard


# =============================================================================
# ASCII VISUALIZERS — used by the coverage backdrop
# =============================================================================

def render_ascii_cube(ir: "KnowledgeIR") -> list[str]:
    """ASCII visualization of the 3-cube with filled/empty status per cell.

    Shows the 8 vertices (v0-v7) at the corners with fill markers, the 12 edges
    labeled across the middle, the 6 faces listed below, and the volume at
    the bottom. Fill marker: `[X]` if placed, `[ ]` if empty.
    """
    placed = ir.cells_with_placements() if ir.cube is not None else set()

    def mark(label: str) -> str:
        return "X" if label in placed else " "

    lines: list[str] = []
    lines.append("3-cube combinatorial complex (F_2^3)")
    lines.append("")
    lines.append("            v6[{}]───────e6-7───────v7[{}]".format(mark("v6"), mark("v7")))
    lines.append("            /│                      /│")
    lines.append("         e2-6                    e3-7")
    lines.append("          /  │                    /  │")
    lines.append("       v2[{}]──────e2-3────────v3[{}] │".format(mark("v2"), mark("v3")))
    lines.append("        │   e4-6                 │   e5-7")
    lines.append("        │    │        Volume     │    │")
    lines.append("      e0-2   │         V[{}]      e1-3 │".format(mark("V")))
    lines.append("        │  v4[{}]─────e4-5───────│──v5[{}]".format(mark("v4"), mark("v5")))
    lines.append("        │   /                    │   /")
    lines.append("        │ e0-4                   │ e1-5")
    lines.append("        │ /                      │ /")
    lines.append("       v0[{}]───────e0-1────────v1[{}]".format(mark("v0"), mark("v1")))
    lines.append("")
    lines.append("Faces (6): " + "  ".join(
        f"{lbl}[{mark(lbl)}]" for lbl in ("f0-0", "f0-1", "f1-0", "f1-1", "f2-0", "f2-1")
    ))
    return lines


def render_rank_bars(ir: "KnowledgeIR") -> list[str]:
    """f-vector + per-rank coverage as ASCII horizontal bars."""
    lines: list[str] = []
    cube = ir.cube
    if cube is None:
        lines.append("(no cube attached)")
        return lines

    rank_names = {0: "unit       (vertex)", 1: "integration(edge)  ",
                  2: "interface  (face)  ", 3: "e2e        (volume)"}
    placed = ir.cells_with_placements()
    counts = cube.cell_count()

    lines.append(f"{'':<28} placed/total   bar")
    lines.append(f"{'':-<28}{'':-<15}{'':-<32}")
    for r in sorted(counts):
        total = counts[r]
        if total == 0:
            continue
        covered = sum(
            1 for c in cube.cells_by_rank[r] if c.label in placed
        )
        frac = covered / total
        filled = int(round(frac * 28))
        bar = "█" * filled + "░" * (28 - filled)
        lines.append(
            f"rank {r} {rank_names.get(r, '?'):<20} "
            f"{covered:>3}/{total:<3}      {bar}  {frac * 100:.0f}%"
        )
    total_covered = sum(
        sum(1 for c in cube.cells_by_rank[r] if c.label in placed)
        for r in counts
    )
    total_cells = sum(counts.values())
    overall_frac = total_covered / total_cells if total_cells else 0
    lines.append("")
    lines.append(f"{'TOTAL':<28} {total_covered:>3}/{total_cells:<3}      "
                 f"{'█' * int(round(overall_frac * 28)) + '░' * (28 - int(round(overall_frac * 28)))}  "
                 f"{overall_frac * 100:.0f}%")
    lines.append("")
    lines.append(f"f-vector: {tuple(counts[r] for r in sorted(counts))}")
    return lines


# =============================================================================
# DATUM-FIRST REPORT
# =============================================================================

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def render_datum_report(
    ir: "KnowledgeIR",
    instances: list,
    profile: Optional["ProfileCard"] = None,
    top_n_gaps: int = 3,
) -> str:
    """Render the datum-first semantic-coverage report as markdown."""
    lines: list[str] = []

    title = f"Semantic Coverage Report — v0 — {datetime.now(tz=timezone.utc).date().isoformat()}"
    lines.append(f"# {title}")
    lines.append("")

    # Profile Card
    if profile is not None:
        lines.append("## Profile")
        lines.append("")
        lines.append(f"- **Name**: {profile.name or '(not inferable)'}")
        if profile.primary_purpose:
            lines.append(f"- **Primary purpose**: {profile.primary_purpose}")
        if profile.domain:
            lines.append(f"- **Domain**: {profile.domain}")
        if profile.dominant_language:
            lines.append(f"- **Dominant language**: `{profile.dominant_language}`")
        if profile.stakeholders:
            lines.append(f"- **Stakeholders**: {', '.join(profile.stakeholders)}")
        if profile.maturity:
            lines.append(f"- **Maturity (source_type counts)**: "
                         f"{_format_count_dict(profile.maturity)}")
        lines.append("")

    # Axis convention
    if ir.axis_convention:
        lines.append("## Axis convention")
        lines.append("")
        for slot in sorted(ir.axis_convention):
            lines.append(f"- slot {slot}: **{ir.axis_convention[slot]}**")
        lines.append("")

    # Ingest summary
    lines.append("## Observations")
    lines.append("")
    lines.append(f"- Candidates ingested: **{len(ir.candidates)}**")
    lines.append(f"- Placements committed: **{ir.placement_count()}** "
                 f"across **{len(ir.cells_with_placements())}** cells")
    lines.append(f"- Datum instances emitted: **{len(instances)}**")
    lines.append(f"- Provenance chain length: **{len(ir.provenance)}**")
    lines.append(f"- State fingerprint: `{ir.fingerprint()}`")
    lines.append("")

    # Findings by severity
    if instances:
        by_severity = sorted(
            instances,
            key=lambda i: (SEVERITY_ORDER.get(i.severity, 99), i.datum_qualified_name),
        )

        # Group by datum family / name
        by_name: dict[str, list] = {}
        for inst in by_severity:
            by_name.setdefault(inst.datum_qualified_name, []).append(inst)

        lines.append("## Findings")
        lines.append("")
        for name in sorted(by_name):
            insts = by_name[name]
            lines.append(f"### `{name}` — {len(insts)} instance(s)")
            lines.append("")
            for inst in insts[:10]:  # cap per datum
                lines.append(f"- **[{inst.severity}]** {inst.claim}")
                if inst.cell_refs:
                    lines.append(f"  - cells: {', '.join(sorted(inst.cell_refs))}")
                if inst.source_refs:
                    cited = ", ".join(f"`{s}`" for s in sorted(inst.source_refs))
                    lines.append(f"  - citations: {cited}")
                if inst.recommended_action:
                    lines.append(f"  - recommended: {inst.recommended_action}")
                lines.append("")
            if len(insts) > 10:
                lines.append(f"... and {len(insts) - 10} more for `{name}`.")
                lines.append("")
    else:
        lines.append("## Findings")
        lines.append("")
        lines.append("_No datum instances emitted on this run. This typically means one of:_")
        lines.append("- The candidate pool is too small or too homogeneous to trigger the "
                     "registered datums (e.g., no prose<->code edges).")
        lines.append("- All fixtures are fresh (no staleness signal).")
        lines.append("- The staleness thresholds haven't been crossed yet.")
        lines.append("")

    # Proposed gaps
    gaps = _select_proposed_gaps(instances, top_n_gaps)
    if gaps:
        lines.append("## Proposed gaps (top {})".format(len(gaps)))
        lines.append("")
        for i, g in enumerate(gaps, 1):
            lines.append(f"{i}. **{g.datum_qualified_name}** — {g.claim}")
            if g.recommended_action:
                lines.append(f"   _Action:_ {g.recommended_action}")
            lines.append("")
    else:
        lines.append("## Proposed gaps")
        lines.append("")
        lines.append("_None surfaced this run._")
        lines.append("")

    # References
    lines.append("## Full data")
    lines.append("")
    lines.append("- Signed datapoint stream: `.cube/datapoints.jsonl`")
    lines.append("- Candidate pool:           `.cube/candidates.jsonl`")
    lines.append("- Axis convention:          `.cube/axis_convention.json`")
    lines.append("- Coverage backdrop:        `coverage.md`")
    lines.append("")

    return "\n".join(lines) + "\n"


# =============================================================================
# COVERAGE BACKDROP
# =============================================================================

def render_coverage_backdrop(
    ir: "KnowledgeIR",
    metric_results: list,
    profile: Optional["ProfileCard"] = None,
) -> str:
    """Render the coverage + vacuum + frustration + richness backdrop.

    Includes ASCII cube + f-vector + rank bars so the structural content is
    legible at a glance, not buried in tables.
    """
    lines: list[str] = []
    title = f"Structural Backdrop — v0 — {datetime.now(tz=timezone.utc).date().isoformat()}"
    lines.append(f"# {title}")
    lines.append("")
    lines.append("_Backdrop to the datum-first report. Datums are the product; "
                 "this section renders the substrate's raw measurements._")
    lines.append("")

    if profile is not None:
        lines.append("## Profile snapshot")
        lines.append("")
        if profile.name:
            lines.append(f"- **{profile.name}**")
        if profile.primary_purpose:
            lines.append(f"- {profile.primary_purpose}")
        lines.append("")

    # ASCII cube visualization
    lines.append("## Cube state — ASCII view")
    lines.append("")
    lines.append("```")
    lines.extend(render_ascii_cube(ir))
    lines.append("```")
    lines.append("")

    # f-vector + rank bars
    lines.append("## f-vector & rank coverage")
    lines.append("")
    lines.append("```")
    lines.extend(render_rank_bars(ir))
    lines.append("```")
    lines.append("")

    # Each metric in its own section
    by_name = {r.name: r for r in metric_results}

    if "coverage" in by_name:
        r = by_name["coverage"]
        lines.append("## Coverage")
        lines.append("")
        lines.append(f"> {r.summary}")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for k in sorted(r.scalars):
            lines.append(f"| `{k}` | {r.scalars[k]} |")
        lines.append("")

    if "vacuum" in by_name:
        r = by_name["vacuum"]
        lines.append("## Vacuums")
        lines.append("")
        lines.append(f"> {r.summary}")
        lines.append("")
        vacuum_cells = sorted(
            cell for cell, reading in r.cell_readings.items()
            if reading.get("is_vacuum")
        )
        if vacuum_cells:
            lines.append("**Empty cells**:")
            lines.append("")
            for cell in vacuum_cells[:25]:
                lines.append(f"- `{cell}`")
            if len(vacuum_cells) > 25:
                lines.append(f"- ... and {len(vacuum_cells) - 25} more")
            lines.append("")

    if "frustration" in by_name:
        r = by_name["frustration"]
        lines.append("## Frustrations")
        lines.append("")
        lines.append(f"> {r.summary}")
        lines.append("")
        if r.cell_readings:
            for cell, reading in sorted(r.cell_readings.items()):
                lines.append(f"- `{cell}`: {reading}")
            lines.append("")
        else:
            lines.append("_No frustrated cells on this run._")
            lines.append("")

    if "richness" in by_name:
        r = by_name["richness"]
        lines.append("## Richness")
        lines.append("")
        lines.append(f"> {r.summary}")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for k in sorted(r.scalars):
            lines.append(f"| `{k}` | {r.scalars[k]} |")
        lines.append("")

    # IR fingerprint
    lines.append("## State identity")
    lines.append("")
    lines.append(f"- State fingerprint: `{ir.fingerprint()}`")
    lines.append(f"- Observed at: {ir.observed_at}")
    lines.append("")

    return "\n".join(lines) + "\n"


# =============================================================================
# HELPERS
# =============================================================================

def _format_count_dict(d: dict) -> str:
    parts = [f"`{k}`: {v}" for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))]
    return ", ".join(parts)


def _select_proposed_gaps(instances: list, top_n: int) -> list:
    """Select the top-N highest-severity, most-cited datum instances as
    'proposed gaps' the report emphasizes for actioning."""
    if not instances:
        return []
    ranked = sorted(
        instances,
        key=lambda i: (SEVERITY_ORDER.get(i.severity, 99), -len(i.source_refs)),
    )
    seen_names = set()
    out: list = []
    # Prefer diversity across datum names so we don't fill gaps with three
    # instances of the same kind
    for inst in ranked:
        if inst.datum_qualified_name not in seen_names:
            out.append(inst)
            seen_names.add(inst.datum_qualified_name)
            if len(out) >= top_n:
                break
    if len(out) < top_n:
        for inst in ranked:
            if inst not in out:
                out.append(inst)
                if len(out) >= top_n:
                    break
    return out
