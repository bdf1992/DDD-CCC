"""
Combinatorial Complex: Minimal Running Cell
===========================================

Purpose
-------
Answer one question: does the "combinatorial complex with embedded algebras"
framing have operational content, or is it label-only?

The check is a single concrete cell of a combinatorial complex, with an
attached algebra (stalk), together with one face map to a sub-cell, and a
compatibility check that the face map is a module homomorphism. If this file
runs end-to-end and the check passes, the framing has at least one running
spoke. If it does not, the framing is cut back to vocabulary.

The construction
----------------
Base combinatorial complex: the Fano plane PG(2, 2).
    - Rank 0 cells: the FANO = 7 points.
    - Rank 1 cells: the FANO = 7 lines (each containing V = 3 points).
    - Incidence: a point is a face of a line iff the point lies on the line.

Algebra stalks:
    - Stalk at each rank-0 cell: Z / N_VALUES (the crumb ring, 4 elements).
    - Stalk at each rank-1 cell: (Z / N_VALUES) ^ V (a V-tuple of crumbs,
      one slot for each point incident to the line).

Face map:
    For a line L with incident points (p_0, p_1, p_2) and a target point p_k
    on L, the face map restricts the line's stalk to the point's stalk by
    projecting the V-tuple onto its k-th component:

        pi_{L -> p_k} : (a_0, a_1, a_2) |-> a_k

Compatibility
-------------
The face map is required to be a Z / N_VALUES-module homomorphism:
    pi(0) = 0
    pi(a + b) = pi(a) + pi(b)
    pi(r * a) = r * pi(a)
The check is exhaustive over all pairs (a, b) in the line stalk (N_VALUES ^ V
elements, so N_VALUES^(2V) = 4096 additive pairs) and all scalars.

If the check passes, the spoke registers under the "Combinatorial Complex"
hub in the code wiki.

Run
---
    python s3/combinatorial_complex.py

Artifact
--------
    witness/combinatorial_complex/fano_cc_report.txt
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
import sys

# Stand on primitives (single source of truth). Do not hardcode V, FANO, N_VALUES.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from primitives import V, FANO, N_VALUES  # V=3, FANO=7, N_VALUES=4


# -----------------------------------------------------------------------------
# Fano plane PG(2, 2) — 7 points and 7 lines, a Singer difference-set labeling
# -----------------------------------------------------------------------------
FANO_POINTS: tuple[int, ...] = tuple(range(FANO))
FANO_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 3),
    (1, 2, 4),
    (2, 3, 5),
    (3, 4, 6),
    (4, 5, 0),
    (5, 6, 1),
    (6, 0, 2),
)

# Structural sanity (these are the defining properties of a projective plane):
assert len(FANO_LINES) == FANO, f"expected {FANO} lines, got {len(FANO_LINES)}"
for _line in FANO_LINES:
    assert len(_line) == V, f"each line must have V={V} points; got {_line}"
# Every pair of distinct points lies on exactly one line.
_pair_count: dict[tuple[int, int], int] = {}
for _line in FANO_LINES:
    _pts = sorted(_line)
    for _i in range(V):
        for _j in range(_i + 1, V):
            _k = (_pts[_i], _pts[_j])
            _pair_count[_k] = _pair_count.get(_k, 0) + 1
for _pair, _count in _pair_count.items():
    assert _count == 1, f"pair {_pair} is on {_count} lines, expected exactly 1"
del _pair_count, _line, _pts, _i, _j, _k, _pair, _count


# -----------------------------------------------------------------------------
# Cells and the combinatorial complex
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Cell:
    """A cell in the combinatorial complex. Identity is (label, rank)."""
    label: str
    rank: int


@dataclass
class FanoCC:
    """The Fano plane as a combinatorial complex.

    - `cells`       : all rank-0 and rank-1 cells.
    - `incidence`   : for each rank-0 cell (point), the set of rank-1 cells
                      (lines) that contain it. A point is a FACE of a line iff
                      the line is in incidence[point].
    - `line_points` : for each rank-1 cell (line), the ordered tuple of rank-0
                      cells incident to it. The order determines how the line
                      stalk's components align with point stalks.
    """
    cells: list[Cell]
    incidence: dict[Cell, frozenset[Cell]]
    line_points: dict[Cell, tuple[Cell, ...]]


def build_fano_cc() -> FanoCC:
    points = [Cell(label=f"p{p}", rank=0) for p in FANO_POINTS]
    lines = [Cell(label=f"L{i}", rank=1) for i in range(FANO)]
    cells = points + lines
    incidence: dict[Cell, frozenset[Cell]] = {}
    line_points: dict[Cell, tuple[Cell, ...]] = {}
    for i, line_pt_indices in enumerate(FANO_LINES):
        line_cell = lines[i]
        line_points[line_cell] = tuple(points[j] for j in line_pt_indices)
    for p_idx, p_cell in enumerate(points):
        incident_lines = frozenset(
            lines[i] for i, line_pt_indices in enumerate(FANO_LINES)
            if p_idx in line_pt_indices
        )
        incidence[p_cell] = incident_lines
    return FanoCC(cells=cells, incidence=incidence, line_points=line_points)


# -----------------------------------------------------------------------------
# Algebra stalks: Z/N_VALUES on points, (Z/N_VALUES)^V on lines
# -----------------------------------------------------------------------------
class PointStalk:
    """Z / N_VALUES as a module over itself."""
    n = N_VALUES

    @classmethod
    def zero(cls) -> int:
        return 0

    @classmethod
    def add(cls, a: int, b: int) -> int:
        return (a + b) % cls.n

    @classmethod
    def scale(cls, r: int, a: int) -> int:
        return (r * a) % cls.n

    @classmethod
    def elements(cls) -> list[int]:
        return list(range(cls.n))


class LineStalk:
    """(Z / N_VALUES)^V as a module over Z / N_VALUES (component-wise)."""
    n = N_VALUES
    arity = V

    @classmethod
    def zero(cls) -> tuple[int, ...]:
        return tuple(0 for _ in range(cls.arity))

    @classmethod
    def add(cls, a: tuple[int, ...], b: tuple[int, ...]) -> tuple[int, ...]:
        return tuple((x + y) % cls.n for x, y in zip(a, b))

    @classmethod
    def scale(cls, r: int, a: tuple[int, ...]) -> tuple[int, ...]:
        return tuple((r * x) % cls.n for x in a)

    @classmethod
    def elements(cls) -> list[tuple[int, ...]]:
        return [tuple(t) for t in product(range(cls.n), repeat=cls.arity)]


# -----------------------------------------------------------------------------
# Face map: restriction from a line's stalk to an incident point's stalk
# -----------------------------------------------------------------------------
def build_face_map(line: Cell, target: Cell, cc: FanoCC):
    """Return the restriction morphism pi : LineStalk -> PointStalk.

    pi((a_0, ..., a_{V-1})) = a_k where k is the position of `target` in the
    ordered tuple cc.line_points[line].

    Raises ValueError if `target` is not incident to `line`.
    """
    pts = cc.line_points[line]
    if target not in pts:
        raise ValueError(f"{target.label} is not a face of {line.label}")
    k = pts.index(target)

    def pi(x: tuple[int, ...]) -> int:
        return x[k]

    pi.index = k  # attach for reporting
    return pi


# -----------------------------------------------------------------------------
# Compatibility check: pi is a Z/N_VALUES-module homomorphism
# -----------------------------------------------------------------------------
def check_module_hom(pi) -> tuple[bool, str]:
    """Exhaustively verify pi : LineStalk -> PointStalk is a module hom."""
    if pi(LineStalk.zero()) != PointStalk.zero():
        return False, "pi(0) != 0"
    for a in LineStalk.elements():
        for b in LineStalk.elements():
            if pi(LineStalk.add(a, b)) != PointStalk.add(pi(a), pi(b)):
                return False, f"additivity failed at a={a}, b={b}"
    for r in range(N_VALUES):
        for a in LineStalk.elements():
            if pi(LineStalk.scale(r, a)) != PointStalk.scale(r, pi(a)):
                return False, f"scalar compatibility failed at r={r}, a={a}"
    return True, "pi is a Z/N_VALUES-module homomorphism (exhaustively verified)"


# -----------------------------------------------------------------------------
# Distinction operator D : Cell -> (identity, faces, cofaces)
# -----------------------------------------------------------------------------
# Committed signature (one action, three things, in order):
#
#     D(cell) = (identity, faces, cofaces)
#
#   - identity : the zero element of the stalk algebra attached to this cell.
#                Reads as "what this cell IS as an algebraic object."
#   - faces    : the rank-(k-1) cells that are sub-cells of this rank-k cell.
#                Reads as "what this cell CONTAINS."
#   - cofaces  : the rank-(k+1) cells that contain this rank-k cell.
#                Reads as "what CONTAINS this cell."
#
# The three slots encode the cell's self-content, its downward structure, and
# its upward structure — the minimum structural portrait of a cell in a
# ranked combinatorial complex. Applied once to any cell, exactly three
# things come out, in this order. This operationalizes the thread claim
# "one distinction creates three things out of one action" as a concrete,
# testable signature. The statement is now falsifiable: if applied to a
# cell this function returns more or fewer than three things, or returns
# them in a different order, the claim is violated.

@dataclass(frozen=True)
class DistinctionResult:
    """The three things produced by one application of D."""
    identity: object                       # stalk zero for the cell's rank
    faces: frozenset                       # sub-cells (rank k-1)
    cofaces: frozenset                     # super-cells (rank k+1)


def distinction(cell: Cell, cc: FanoCC) -> DistinctionResult:
    """Apply the distinction operator D to `cell` inside the Fano CC.

    Returns a DistinctionResult — a 3-field structure whose slots are
    (identity, faces, cofaces), in that fixed order. One action, three
    things.
    """
    if cell.rank == 0:
        ident: object = PointStalk.zero()
        faces: frozenset = frozenset()
        cofaces: frozenset = cc.incidence.get(cell, frozenset())
    elif cell.rank == 1:
        ident = LineStalk.zero()
        faces = frozenset(cc.line_points[cell])
        cofaces = frozenset()
    else:
        raise ValueError(f"unsupported rank {cell.rank} for distinction")
    return DistinctionResult(identity=ident, faces=faces, cofaces=cofaces)


def check_distinction_signature(cc: FanoCC) -> tuple[bool, str]:
    """Verify that D returns exactly three things with the right shapes.

    Requirements:
      - Every rank-0 cell has V cofaces (incident lines) and 0 faces.
      - Every rank-1 cell has V faces (incident points) and 0 cofaces.
      - The identity slot matches the stalk type for the cell's rank.
    """
    for cell in cc.cells:
        result = distinction(cell, cc)
        # Three-slot invariance: the dataclass has exactly three fields.
        if len(result.__dataclass_fields__) != V:
            return False, (
                f"distinction result has {len(result.__dataclass_fields__)} "
                f"fields; expected {V}"
            )
        if cell.rank == 0:
            if len(result.cofaces) != V:
                return False, f"{cell.label} has {len(result.cofaces)} cofaces, expected {V}"
            if len(result.faces) != 0:
                return False, f"{cell.label} has {len(result.faces)} faces, expected 0"
            if result.identity != 0:
                return False, f"{cell.label} identity != 0"
        elif cell.rank == 1:
            if len(result.faces) != V:
                return False, f"{cell.label} has {len(result.faces)} faces, expected {V}"
            if len(result.cofaces) != 0:
                return False, f"{cell.label} has {len(result.cofaces)} cofaces, expected 0"
            if result.identity != tuple(0 for _ in range(V)):
                return False, f"{cell.label} identity != (0,0,0)"
    return True, f"distinction returns (identity, faces, cofaces) with the right shape for all {len(cc.cells)} cells"


# -----------------------------------------------------------------------------
# Unfolding from a seed: D applied iteratively reaches the whole complex
# -----------------------------------------------------------------------------
def unfold_from(seed: Cell, cc: FanoCC) -> tuple[frozenset[Cell], int]:
    """Starting from `seed`, repeatedly apply D and collect every cell
    that appears in any face or coface slot, until no new cells appear.

    Returns (reached_cells, rounds). `rounds` is the number of D-application
    layers needed before the frontier saturates.
    """
    reached: set[Cell] = {seed}
    frontier: set[Cell] = {seed}
    rounds = 0
    while frontier:
        new_frontier: set[Cell] = set()
        for cell in frontier:
            result = distinction(cell, cc)
            for c in result.faces | result.cofaces:
                if c not in reached:
                    reached.add(c)
                    new_frontier.add(c)
        frontier = new_frontier
        if new_frontier:
            rounds += 1
    return frozenset(reached), rounds


def check_unfolding_reaches_all(cc: FanoCC, seed: Cell) -> tuple[bool, str]:
    reached, rounds = unfold_from(seed, cc)
    total = len(cc.cells)
    if len(reached) != total:
        missing = set(cc.cells) - set(reached)
        return False, f"unfolding from {seed.label} reached {len(reached)}/{total}, missing {[c.label for c in missing]}"
    return True, f"unfolding from {seed.label} reached all {total} cells in {rounds} rounds of D"


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------
def main() -> int:
    cc = build_fano_cc()
    n_rank_0 = sum(1 for c in cc.cells if c.rank == 0)
    n_rank_1 = sum(1 for c in cc.cells if c.rank == 1)
    assert n_rank_0 == FANO and n_rank_1 == FANO

    # Pick one concrete (line, point) pair and run the face map check.
    line_cell = next(c for c in cc.cells if c.label == "L0")
    target_cell = cc.line_points[line_cell][0]  # first point on L0 in the ordering
    pi = build_face_map(line_cell, target_cell, cc)
    ok_homom, reason_homom = check_module_hom(pi)

    # Distinction operator checks.
    ok_sig, reason_sig = check_distinction_signature(cc)
    seed_cell = next(c for c in cc.cells if c.label == "p0")
    ok_unfold, reason_unfold = check_unfolding_reaches_all(cc, seed_cell)

    # Run D once on the seed and extract the three things for the report.
    seed_result = distinction(seed_cell, cc)
    seed_cofaces_labels = sorted(c.label for c in seed_result.cofaces)

    # Compose the report.
    report_lines: list[str] = []
    report_lines.append("Combinatorial Complex — Fano Plane with Crumb Stalks")
    report_lines.append("=" * 60)
    report_lines.append(f"Constants (from primitives.py):")
    report_lines.append(f"  V        = {V}")
    report_lines.append(f"  FANO     = {FANO}")
    report_lines.append(f"  N_VALUES = {N_VALUES}")
    report_lines.append("")
    report_lines.append(f"Cells: {n_rank_0} rank-0 (points) + {n_rank_1} rank-1 (lines) = {n_rank_0 + n_rank_1}")
    report_lines.append("")
    report_lines.append("One rank-0 cell:")
    report_lines.append(f"  label = {target_cell.label}, rank = {target_cell.rank}")
    report_lines.append(f"  stalk = Z/{N_VALUES}   (the crumb ring)")
    report_lines.append("")
    report_lines.append("One rank-1 cell:")
    report_lines.append(f"  label = {line_cell.label}, rank = {line_cell.rank}")
    report_lines.append(f"  incident points (ordered) = {tuple(c.label for c in cc.line_points[line_cell])}")
    report_lines.append(f"  stalk = (Z/{N_VALUES})^{V}")
    report_lines.append("")
    report_lines.append(f"Face map: {line_cell.label} -> {target_cell.label}")
    report_lines.append(f"  pi((a_0, a_1, a_2)) = a_{pi.index}")
    report_lines.append(f"  sample: pi((1, 2, 3)) = {pi((1, 2, 3))}")
    report_lines.append(f"          pi((0, 0, 0)) = {pi((0, 0, 0))}")
    report_lines.append("")
    report_lines.append("Module homomorphism check:")
    report_lines.append(f"  result = {'PASS' if ok_homom else 'FAIL'}")
    report_lines.append(f"  reason = {reason_homom}")
    report_lines.append("")
    report_lines.append("Distinction operator D : Cell -> (identity, faces, cofaces)")
    report_lines.append(f"  signature committed: 3 slots, arity {V}, fixed order")
    report_lines.append(f"  signature check = {'PASS' if ok_sig else 'FAIL'}")
    report_lines.append(f"    {reason_sig}")
    report_lines.append("")
    report_lines.append(f"  D({seed_cell.label}) yields:")
    report_lines.append(f"    identity = {seed_result.identity}    (zero of Z/{N_VALUES})")
    report_lines.append(f"    faces    = {sorted(c.label for c in seed_result.faces) or '(empty — rank 0)'}")
    report_lines.append(f"    cofaces  = {seed_cofaces_labels}")
    report_lines.append("")
    report_lines.append("Unfolding from a seed (iterated application of D):")
    report_lines.append(f"  unfolding check = {'PASS' if ok_unfold else 'FAIL'}")
    report_lines.append(f"    {reason_unfold}")
    report_lines.append("")
    report_lines.append("Fano incidence (each line with its point indices):")
    for i, line_pts in enumerate(FANO_LINES):
        report_lines.append(f"  L{i}: {line_pts}")
    report = "\n".join(report_lines) + "\n"

    ok = ok_homom and ok_sig and ok_unfold

    # Write artifact.
    out_dir = Path(__file__).resolve().parents[1] / "witness" / "combinatorial_complex"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fano_cc_report.txt"
    out_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"Artifact: {out_path}")

    if not ok:
        print("SPOKE CANNOT REGISTER: one or more checks failed.")
        print(f"  module homomorphism: {'PASS' if ok_homom else 'FAIL'}")
        print(f"  distinction signature: {'PASS' if ok_sig else 'FAIL'}")
        print(f"  unfolding reaches all: {'PASS' if ok_unfold else 'FAIL'}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
