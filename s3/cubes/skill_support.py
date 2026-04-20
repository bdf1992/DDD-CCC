"""
skill_support — reference implementations of the four-piece contextual-skill
pattern helpers.

Every authorship skill (`adapter-design`, `datum-design`, `metric-design`, ...)
must fulfill two obligations on every invocation:

  - create-datum    — produce at least one typed, cited datum instance
  - semantic-balance — leave the cube more balanced or surface imbalance

These helpers provide the Piece 2 / Piece 3 / Piece 4 machinery skills compose
from:

  read_cube_context(ir)                  — Piece 2 (context-before-propose)
  balance_check(ir, proposed_placements) — Piece 4 (semantic-balance check)
  network_extension_report(pre, post, module_name, added_datums)
                                         — Piece 3 (datum-first, network-extension output)

Skills import + call these; they are not mandatory but are the canonical
shape. A skill that rolls its own must produce outputs of the same schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Avoid circular imports; KnowledgeIR is duck-typed here.


@dataclass
class CubeContext:
    """What a skill reads before it proposes. Piece 2 output."""
    placed_cells: list[str]
    vacuum_cells: list[str]
    placement_count: int
    n_placed_cells: int
    n_vacuum_cells: int
    load_per_cell: dict[str, int]
    axis_convention: dict[int, str]
    recent_provenance_count: int
    observed_at: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(tz=timezone.utc).isoformat()


@dataclass
class BalanceVerdict:
    """Piece 4 output. `balanced=True` licenses the skill to commit."""
    balanced: bool
    variance: float
    flagged_cells: list[dict]
    recommendation: str
    projected_loads: dict[str, int] = field(default_factory=dict)


@dataclass
class NetworkExtensionReport:
    """Piece 3 output — canonical shape of the skill's bundled output."""
    module_name: str
    volume_added: str
    connected_to: list[dict]
    vacuums_filled: list[str]
    vacuums_revealed: list[str]
    balance_impact: dict
    datum_names: list[str]
    observed_at: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(tz=timezone.utc).isoformat()

    def as_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "volume_added": self.volume_added,
            "connected_to": self.connected_to,
            "vacuums_filled": self.vacuums_filled,
            "vacuums_revealed": self.vacuums_revealed,
            "balance_impact": self.balance_impact,
            "datum_names": self.datum_names,
            "observed_at": self.observed_at,
        }


def read_cube_context(ir) -> CubeContext:
    """Summarize the cube's current state for a skill's context-before-propose
    step. Duck-typed on KnowledgeIR.

    Returns placed cells, vacuum cells, load distribution, axis convention,
    and recent provenance count — enough for the skill to shape its proposal.
    """
    placements = dict(getattr(ir, "placements", {}) or {})
    all_cell_labels: set[str] = set(placements.keys())
    if getattr(ir, "cube", None) is not None:
        cube = ir.cube
        for cell in getattr(cube, "cells", []) or []:
            label = getattr(cell, "label", None) or str(cell)
            all_cell_labels.add(label)

    placed = sorted(label for label, ids in placements.items() if ids)
    vacuum = sorted(all_cell_labels - set(placed))
    load = {label: len(ids) for label, ids in placements.items() if ids}
    axis = dict(getattr(ir, "axis_convention", {}) or {})
    provenance = list(getattr(ir, "provenance", []) or [])

    return CubeContext(
        placed_cells=placed,
        vacuum_cells=vacuum,
        placement_count=sum(load.values()),
        n_placed_cells=len(placed),
        n_vacuum_cells=len(vacuum),
        load_per_cell=load,
        axis_convention=axis,
        recent_provenance_count=len(provenance),
    )


def balance_check(ir, proposed_placements: dict[str, int],
                  threshold_multiplier: float = 3.0) -> BalanceVerdict:
    """Semantic-balance check (Piece 4).

    `proposed_placements` : dict[cell_label -> n_added]. The skill projects
        how many new candidates would land on each cell if it commits.
    `threshold_multiplier`: a cell is flagged when its projected load exceeds
        `threshold_multiplier × median_projected_load` (and absolute count ≥ 3).
        Default 3.0 is chosen to let small runs pass while catching bulk dumps.

    Returns a verdict; skills must refuse to commit if `balanced=False`
    without surfacing the recommendation to the user.
    """
    ctx = read_cube_context(ir)
    projected = dict(ctx.load_per_cell)
    for label, n in (proposed_placements or {}).items():
        projected[label] = projected.get(label, 0) + int(n)

    loads = sorted(projected.values())
    if not loads:
        return BalanceVerdict(balanced=True, variance=0.0,
                              flagged_cells=[],
                              recommendation="no placements yet; nothing to balance",
                              projected_loads=projected)

    median = loads[len(loads) // 2]
    mean = sum(loads) / len(loads)
    variance = sum((x - mean) ** 2 for x in loads) / len(loads)

    flagged: list[dict] = []
    for label, load in projected.items():
        if load >= 3 and load > threshold_multiplier * max(median, 1):
            flagged.append({
                "cell": label,
                "projected_load": load,
                "median_load": median,
                "factor": round(load / max(median, 1), 2),
            })

    balanced = not flagged
    if balanced:
        recommendation = (f"balanced: variance={variance:.2f}, "
                          f"no cell exceeds {threshold_multiplier}× median")
    else:
        flagged_names = ", ".join(f["cell"] for f in flagged)
        recommendation = (
            f"IMBALANCE: {len(flagged)} cell(s) would exceed "
            f"{threshold_multiplier}× median load: {flagged_names}. "
            f"Consider splitting the proposal across adapters / datums / "
            f"a finer cell rank, or ask the user before committing."
        )
    return BalanceVerdict(
        balanced=balanced,
        variance=variance,
        flagged_cells=flagged,
        recommendation=recommendation,
        projected_loads=projected,
    )


def network_extension_report(
    pre_ctx: CubeContext,
    post_ctx: CubeContext,
    module_name: str,
    volume_added: str,
    connected_to: Optional[list[dict]] = None,
    datum_names: Optional[list[str]] = None,
    vacuums_filled: Optional[list[str]] = None,
    vacuums_revealed: Optional[list[str]] = None,
) -> NetworkExtensionReport:
    """Piece 3 — canonical bundle the skill must emit alongside its artifact.

    Most fields are declared by the skill (it knows what it added). The
    balance_impact is computed from the pre/post context diff.
    """
    load_delta: dict[str, int] = {}
    for cell, load in post_ctx.load_per_cell.items():
        pre_load = pre_ctx.load_per_cell.get(cell, 0)
        if load != pre_load:
            load_delta[cell] = load - pre_load

    # Vacuums filled (auto-derivable fallback): cells that were vacuum pre
    # but have placements post.
    pre_vacuum = set(pre_ctx.vacuum_cells)
    post_placed = set(post_ctx.placed_cells)
    auto_filled = sorted(pre_vacuum & post_placed)

    return NetworkExtensionReport(
        module_name=module_name,
        volume_added=volume_added,
        connected_to=list(connected_to or []),
        vacuums_filled=list(vacuums_filled
                            if vacuums_filled is not None
                            else auto_filled),
        vacuums_revealed=list(vacuums_revealed or []),
        balance_impact={
            "cells_touched": sorted(load_delta.keys()),
            "load_delta": load_delta,
            "placement_count_pre": pre_ctx.placement_count,
            "placement_count_post": post_ctx.placement_count,
            "n_placed_cells_pre": pre_ctx.n_placed_cells,
            "n_placed_cells_post": post_ctx.n_placed_cells,
        },
        datum_names=list(datum_names or []),
    )


def render_report_markdown(report: NetworkExtensionReport) -> str:
    """Render a network-extension report as human-readable markdown."""
    lines: list[str] = []
    lines.append(f"# Network-Extension Report — {report.module_name}")
    lines.append("")
    lines.append(f"*Observed at: {report.observed_at}*")
    lines.append("")
    lines.append(f"## Volume added")
    lines.append(f"- **{report.volume_added}**")
    lines.append("")
    lines.append(f"## Connected to (shared face / edge / vertex)")
    if report.connected_to:
        for c in report.connected_to:
            lines.append(f"- {c.get('volume', '?')} — via {c.get('shared_element', '?')} "
                         f"({c.get('rank_of_shared', '?')})")
    else:
        lines.append("- (first volume in the network; no prior connections)")
    lines.append("")
    lines.append(f"## Vacuums filled")
    for v in report.vacuums_filled:
        lines.append(f"- {v}")
    if not report.vacuums_filled:
        lines.append("- (none)")
    lines.append("")
    lines.append(f"## Vacuums revealed")
    for v in report.vacuums_revealed:
        lines.append(f"- {v}")
    if not report.vacuums_revealed:
        lines.append("- (none)")
    lines.append("")
    lines.append(f"## Datum instances produced")
    for d in report.datum_names:
        lines.append(f"- {d}")
    if not report.datum_names:
        lines.append("- (none — WARNING: create-datum obligation not met)")
    lines.append("")
    lines.append(f"## Balance impact")
    bi = report.balance_impact
    lines.append(f"- placements: {bi.get('placement_count_pre')} → "
                 f"{bi.get('placement_count_post')}")
    lines.append(f"- placed cells: {bi.get('n_placed_cells_pre')} → "
                 f"{bi.get('n_placed_cells_post')}")
    lines.append(f"- cells touched: {len(bi.get('cells_touched', []))}")
    if bi.get("load_delta"):
        lines.append("")
        lines.append("```")
        for cell, delta in sorted(bi["load_delta"].items()):
            lines.append(f"  {cell}: +{delta}" if delta > 0 else f"  {cell}: {delta}")
        lines.append("```")
    return "\n".join(lines)


def run_self_test() -> dict:
    """Smoke-test the three helpers against a lightweight stand-in IR."""
    from dataclasses import dataclass as _dc

    @_dc
    class _FakeIR:
        placements: dict
        axis_convention: dict
        provenance: list
        cube: None = None

    empty_ir = _FakeIR(placements={}, axis_convention={}, provenance=[])
    populated = _FakeIR(
        placements={"v0": ["a", "b"], "e1": ["c"], "f2": ["d", "e", "f"]},
        axis_convention={0: "type", 1: "domain"},
        provenance=[{"kind": "place", "hash": "x"}],
    )

    tests: list[tuple[str, bool, object]] = []

    ctx_empty = read_cube_context(empty_ir)
    tests.append(("empty IR placement_count == 0",
                  ctx_empty.placement_count == 0, ctx_empty.placement_count))
    tests.append(("empty IR n_placed_cells == 0",
                  ctx_empty.n_placed_cells == 0, ctx_empty.n_placed_cells))

    ctx_pop = read_cube_context(populated)
    tests.append(("populated placement_count == 6",
                  ctx_pop.placement_count == 6, ctx_pop.placement_count))
    tests.append(("populated n_placed_cells == 3",
                  ctx_pop.n_placed_cells == 3, ctx_pop.n_placed_cells))
    tests.append(("axis_convention captured",
                  ctx_pop.axis_convention == {0: "type", 1: "domain"},
                  ctx_pop.axis_convention))

    balanced = balance_check(populated, {"v0": 1, "e1": 1})
    tests.append(("small balanced proposal passes",
                  balanced.balanced, balanced.recommendation))
    unbalanced = balance_check(populated, {"v0": 50})
    tests.append(("large concentrated proposal flags imbalance",
                  not unbalanced.balanced, unbalanced.flagged_cells))

    pre = ctx_pop
    post = read_cube_context(_FakeIR(
        placements={**populated.placements, "v7": ["g", "h"]},
        axis_convention=populated.axis_convention,
        provenance=populated.provenance,
    ))
    rep = network_extension_report(
        pre, post,
        module_name="fake-adapter",
        volume_added="fake-volume",
        connected_to=[{"volume": "other", "shared_element": "outbound_refs",
                       "rank_of_shared": "face"}],
        datum_names=["fake_datum"],
    )
    tests.append(("report load_delta includes v7",
                  rep.balance_impact["load_delta"].get("v7") == 2,
                  rep.balance_impact["load_delta"]))
    tests.append(("report datum_names non-empty",
                  len(rep.datum_names) == 1, rep.datum_names))
    md = render_report_markdown(rep)
    tests.append(("markdown render contains module name",
                  "fake-adapter" in md, md[:120]))

    failures = [(n, d) for n, ok, d in tests if not ok]
    return {
        "passed": not failures,
        "summary": (f"ok: {len(tests)} assertions" if not failures
                    else f"failed: {len(failures)}/{len(tests)} "
                         f"[{', '.join(n for n, _ in failures)}]"),
        "failures": [{"name": n, "detail": str(d)[:200]} for n, d in failures],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_self_test(), indent=2, default=str))
