"""
RichnessMetric — rank-weighted concept density.

Higher-rank cells with content count more; empty high-rank cells cost more.
Gives a single scalar for "how structurally populated is this cube" plus
per-rank densities.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.metrics.base import MetricResult


class RichnessMetric:
    name = "richness"
    fires_at = frozenset({"sweep", "ci"})

    def measure(self, ir) -> MetricResult:
        cube = ir.cube
        placed_cells = ir.cells_with_placements()

        if cube is None:
            return MetricResult(
                name=self.name,
                scalars={"richness_score": 0.0},
                summary="no cube attached — richness undefined",
            )

        # Rank weight: (rank + 1). Vertex=1, edge=2, face=3, volume=4.
        by_rank_placed: dict[int, int] = {}
        by_rank_total: dict[int, int] = {}
        for r, cells in cube.cells_by_rank.items():
            by_rank_total[r] = len(cells)
            by_rank_placed[r] = sum(1 for c in cells if c.label in placed_cells)

        weighted_covered = 0.0
        weighted_total = 0.0
        for r in by_rank_total:
            w = r + 1
            weighted_total += w * by_rank_total[r]
            weighted_covered += w * by_rank_placed[r]
        score = (weighted_covered / weighted_total) if weighted_total else 0.0

        densities = {
            f"density_rank_{r}": (by_rank_placed[r] / by_rank_total[r]) if by_rank_total[r] else 0.0
            for r in by_rank_total
        }

        scalars = {
            "richness_score": round(score, 6),
            "weighted_covered": round(weighted_covered, 6),
            "weighted_total": round(weighted_total, 6),
            **{k: round(v, 6) for k, v in densities.items()},
        }
        summary = (
            f"richness: {score:.3f} "
            f"(weighted {weighted_covered:.1f}/{weighted_total:.1f})"
        )
        return MetricResult(
            name=self.name,
            scalars=scalars,
            cell_readings={},
            summary=summary,
        )
