"""
CoverageMetric — cell-presence per rank. The line/function/branch coverage
equivalent in the cube framework: rank 0 = unit, rank 1 = integration,
rank 2 = interface, rank 3 = e2e.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.metrics.base import MetricResult


class CoverageMetric:
    name = "coverage"
    fires_at = frozenset({"ingest", "accept", "reject", "modify", "sweep", "ci"})

    def measure(self, ir) -> MetricResult:
        cube = ir.cube
        placed_cells = ir.cells_with_placements()

        if cube is None:
            return MetricResult(
                name=self.name,
                scalars={"coverage_fraction": 0.0},
                summary="no cube attached — coverage undefined",
            )

        by_rank_total: dict[int, int] = {r: len(cs) for r, cs in cube.cells_by_rank.items()}
        by_rank_covered: dict[int, int] = {r: 0 for r in by_rank_total}
        for cell_label in placed_cells:
            cell = cube.cell_by_label(cell_label)
            if cell is None:
                continue
            by_rank_covered[cell.rank] = by_rank_covered.get(cell.rank, 0) + 1

        total = sum(by_rank_total.values())
        covered = sum(by_rank_covered.values())
        frac = (covered / total) if total else 0.0

        cell_readings = {
            c.label: {"rank": c.rank, "placed": c.label in placed_cells}
            for c in cube.all_cells
        }

        scalars = {
            "total_cells": total,
            "covered_cells": covered,
            "coverage_fraction": round(frac, 6),
        }
        for r in by_rank_total:
            scalars[f"coverage_rank_{r}"] = (
                round(by_rank_covered[r] / by_rank_total[r], 6) if by_rank_total[r] else 0.0
            )

        rank_names = {0: "unit", 1: "integration", 2: "interface", 3: "e2e"}
        parts = []
        for r in sorted(by_rank_total):
            name = rank_names.get(r, f"rank{r}")
            parts.append(f"{name}={by_rank_covered[r]}/{by_rank_total[r]}")
        summary = f"coverage: {covered}/{total} cells ({frac:.1%}); {', '.join(parts)}"

        return MetricResult(
            name=self.name,
            scalars=scalars,
            cell_readings=cell_readings,
            summary=summary,
        )
