"""
vacuum_metric_mini — fixture builder for VacuumMetric proofs.

Constructs a minimal KnowledgeIR anchored at the 3-cube combinatorial
complex (27 cells total: 8 vertices + 12 edges + 6 faces + 1 volume) with
three cells populated. Remaining 24 cells are vacuums; that is the signal
VacuumMetric surfaces.

Fixture is Python (not a serialized IR) because IR holds mutable context
and function references that don't pickle cleanly. Shape is stable: any
drift in the cube's cell count changes the expected vacuum_count, which
the test asserts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from s3.cubes.combinatorial_complex import CubeComplex, build_cube_cc
from s3.cubes.ir.graph import KnowledgeIR


@dataclass
class VacuumMetricProofFixture:
    """Fixture bundle for VacuumMetric's four proofs.

    ir                   : KnowledgeIR with cube + three seeded placements
    intentionally_vacant : set of cell labels the user has marked as
                           intentionally excluded from vacuum reporting
    """
    ir: KnowledgeIR
    intentionally_vacant: frozenset = frozenset()


def build_fixture(intentionally_vacant: frozenset = frozenset()) -> VacuumMetricProofFixture:
    cube = build_cube_cc()
    ir = KnowledgeIR(cube=cube)
    # Seed three placements: 2 vertex, 1 edge. Labels come from the cube
    # itself so they stay consistent with combinatorial_complex.py.
    vertices = sorted(c.label for c in cube.cells_by_rank.get(0, []))
    edges = sorted(c.label for c in cube.cells_by_rank.get(1, []))
    if len(vertices) >= 2:
        ir.place(vertices[0], "seed::v-a")
        ir.place(vertices[1], "seed::v-b")
    if len(edges) >= 1:
        ir.place(edges[0], "seed::e-a")
    return VacuumMetricProofFixture(
        ir=ir,
        intentionally_vacant=frozenset(intentionally_vacant or ()),
    )


def expected_vacuum_count(fixture: VacuumMetricProofFixture) -> int:
    """Expected vacuum count after applying intentionally_vacant exclusion."""
    cube = fixture.ir.cube
    total_cells = sum(len(cs) for cs in cube.cells_by_rank.values())
    placed = len(fixture.ir.cells_with_placements())
    raw_vacuum = total_cells - placed
    # intentionally_vacant cells are STILL vacuums but datum runner excludes them
    return raw_vacuum


def expected_datum_count(fixture: VacuumMetricProofFixture) -> int:
    """Datum count after corrective whitelist."""
    raw = expected_vacuum_count(fixture)
    excluded = len(fixture.intentionally_vacant)
    return raw - excluded


if __name__ == "__main__":
    f = build_fixture()
    print(f"total cells: {sum(len(cs) for cs in f.ir.cube.cells_by_rank.values())}")
    print(f"placed: {len(f.ir.cells_with_placements())}")
    print(f"vacuum count (expected): {expected_vacuum_count(f)}")
