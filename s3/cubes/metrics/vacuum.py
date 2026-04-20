"""
VacuumMetric — empty cells per rank. A vacuum is a cell carrying no content;
collectively they are the untested-territory signal. Feeds the dashboard
and downstream datums (e.g., `vacuum_cell` primitive, `spec_never_implemented`).

Ships module-level PROOF + DEFAULT_CORRECTION_EVENT. Reference metric for
the metric-design skill — analogous to ObsidianVaultAdapter for adapter-design.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.metrics.base import MetricResult


class VacuumMetric:
    name = "vacuum"
    fires_at = frozenset({"ingest", "accept", "reject", "modify", "sweep", "ci"})

    def measure(self, ir) -> MetricResult:
        cube = ir.cube
        placed_cells = ir.cells_with_placements()

        if cube is None:
            return MetricResult(
                name=self.name,
                scalars={"vacuum_count": 0},
                summary="no cube attached — vacuum undefined",
            )

        vacuums_by_rank: dict[int, list[str]] = {}
        for r, cells in cube.cells_by_rank.items():
            vacuums_by_rank[r] = sorted(c.label for c in cells if c.label not in placed_cells)

        cell_readings = {}
        for r, labels in vacuums_by_rank.items():
            for lbl in labels:
                cell_readings[lbl] = {"rank": r, "is_vacuum": True}

        scalars = {
            "vacuum_count": sum(len(v) for v in vacuums_by_rank.values()),
        }
        for r, labels in vacuums_by_rank.items():
            scalars[f"vacuum_rank_{r}"] = len(labels)

        parts = [f"rank_{r}={len(v)}" for r, v in sorted(vacuums_by_rank.items())]
        summary = f"vacuums: {scalars['vacuum_count']} empty cells; {', '.join(parts)}"

        return MetricResult(
            name=self.name,
            scalars=scalars,
            cell_readings=cell_readings,
            summary=summary,
        )


# ============================================================================
# PROOF — four proofs for VacuumMetric.
# ============================================================================

def _measure_fixture(fixture) -> MetricResult:
    """Run the metric against the fixture's IR."""
    metric = VacuumMetric()
    return metric.measure(fixture.ir)


def _cells_filtered(cell_readings: dict, intentionally_vacant) -> dict:
    """Apply the intentionally_vacant exclusion to cell_readings."""
    return {
        label: reading
        for label, reading in cell_readings.items()
        if label not in (intentionally_vacant or frozenset())
    }


def _run_pressure(fixture) -> dict:
    result = _measure_fixture(fixture)
    filtered = _cells_filtered(result.cell_readings, fixture.intentionally_vacant)
    cells_by_rank: dict[int, list[str]] = {}
    for label, reading in filtered.items():
        cells_by_rank.setdefault(reading["rank"], []).append(label)
    return {
        "metric_name": "vacuum",
        "cells": sorted(filtered.keys()),
        "threshold": 0,   # any empty cell is a vacuum
        "fires_at": sorted(VacuumMetric.fires_at),
        "witness": {
            "vacuum_count": len(filtered),
            "by_rank": {r: len(cs) for r, cs in sorted(cells_by_rank.items())},
            "n_excluded_intentional": len(fixture.intentionally_vacant),
        },
    }


def _run_datum(fixture) -> list[dict]:
    result = _measure_fixture(fixture)
    filtered = _cells_filtered(result.cell_readings, fixture.intentionally_vacant)
    instances: list[dict] = []
    for label, reading in sorted(filtered.items()):
        instances.append({
            "name": "vacuum_cell",
            "value": label,
            "cell_refs": [label],
            "evidence": {
                "cell": label,
                "rank": reading["rank"],
                "placement_count_observed": 0,
                "cube_total_cells": sum(
                    len(cs) for cs in fixture.ir.cube.cells_by_rank.values()
                ),
                "metric_scalar_vacuum_count": result.scalars.get("vacuum_count"),
                "excluded_from_report": sorted(fixture.intentionally_vacant),
            },
            "severity": "info",
            "recommended_action": (
                f"place at least one candidate on {label} (rank "
                f"{reading['rank']}), or mark it intentionally_vacant via "
                f"the metric corrective"
            ),
        })
    return instances


def _run_corrective(fixture, correction_event: dict) -> dict:
    from s3.cubes.skill_tests.fixtures.vacuum_metric_mini.fixture import (
        VacuumMetricProofFixture,
    )
    new_terms = frozenset(correction_event.get("intentionally_vacant", ()))
    baseline = frozenset(fixture.intentionally_vacant or ())
    combined = baseline | new_terms
    before = len(_run_datum(fixture))
    after_fixture = VacuumMetricProofFixture(
        ir=fixture.ir, intentionally_vacant=combined
    )
    after = len(_run_datum(after_fixture))
    return {
        "before": before,
        "after": after,
        "intentionally_vacant_before": sorted(baseline),
        "intentionally_vacant_after": sorted(combined),
        "new_terms_applied": sorted(new_terms - baseline),
    }


def _build_proof():
    from s3.cubes.proofs import ProofDeclaration
    return ProofDeclaration(
        pressure_claim=(
            "VacuumMetric reveals untested-territory pressure — cells of any "
            "rank with zero candidate placements, per-rank breakdown, one "
            "datum instance per unfilled cell."
        ),
        pressure_runner=_run_pressure,
        datum_name="vacuum_cell",
        datum_runner=_run_datum,
        corrective_runner=_run_corrective,
        code_tests_module="s3.cubes.metrics.tests.vacuum_test",
        skill_test_fixture="s3/cubes/skill_tests/fixtures/vacuum_metric_mini/",
    )


PROOF = _build_proof()


# Default correction event consumed by the metric-proof harness.
# Marks one vacuum vertex as intentionally_vacant → datum count drops by 1.
# Fixture places v0 + v1 (so those are NOT vacuum); v2 is the smallest-label
# vertex that is actually a vacuum in the fixture IR.
DEFAULT_CORRECTION_EVENT = {"intentionally_vacant": ["v2"]}
