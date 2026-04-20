"""
3-cube combinatorial complex — ranks 0, 1, 2, 3 on the F_2^3 cube.

Extends the Combinatorial Complex hub (s3/combinatorial_complex.py) with the
full cube rank structure beyond its Fano-plane (ranks 0/1) instance.

Test-pyramid mapping (load-bearing):
    rank-0 cell (vertex, 8 of them) = unit
    rank-1 cell (edge,  12 of them) = integration
    rank-2 cell (face,   6 of them) = interface
    rank-3 cell (volume, 1 of them) = e2e
Total cells: 27 = 3^3. This is the 3-cube's f-vector reading (8, 12, 6, 1).

Carrier API — every cell is both identity AND axis-against relation:
    distinction_D(cell)      -> (identity, faces, cofaces)
    axis_against(a, b)       -> dict of relation slots (HD, shares_axis, opposite, parallel)
    incidence_neighbors(c)   -> sibling cells at the same rank incident through shared subcells
    opposites(cell)          -> the antipodal cell at the same rank (if one exists)

Recursion: a cell may itself be a cube combinatorial complex. The carrier API
does not commit to or against recursion; callers compose complexes externally.

Constants: inherited from primitives.py (V, D, FANO, Bott, S_V).
    V = 3    — dimensions
    D = 2    — cube halving (faces per axis)
    FANO = 7 — mask / non-zero vertex count
    Bott = 8 — total vertex count = 2^V
    S_V = 12 — edge count = V * 2^(V-1)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from primitives import V, D, FANO, Bott, S_V

# Reuse the Cell primitive from the hub.
from s3.combinatorial_complex import Cell


# =============================================================================
# CELL CONSTRUCTORS
# =============================================================================

def cube_vertices() -> list[Cell]:
    """Return all Bott=8 rank-0 cells, labeled by F_2^3 index as 'v{i}'."""
    return [Cell(label=f"v{i}", rank=0) for i in range(Bott)]


def cube_edges() -> list[Cell]:
    """Return all S_V=12 rank-1 cells: pairs of vertices at HD=1.

    Each edge is labeled 'e{a}-{b}' with a<b. There are exactly V*2^(V-1) = 12 such pairs.
    """
    edges: list[Cell] = []
    for a in range(Bott):
        for b in range(a + 1, Bott):
            if bin(a ^ b).count("1") == 1:
                edges.append(Cell(label=f"e{a}-{b}", rank=1))
    return edges


def cube_faces() -> list[Cell]:
    """Return all 6 rank-2 cells.

    A face of the 3-cube is specified by fixing one of the 3 coordinates to
    0 or 1 — that gives 2 * 3 = 6 faces. Each face contains 4 vertices.
    Labels: 'f{axis}-{val}' where axis in {0,1,2} is the fixed-bit position and
    val in {0,1} is the fixed bit value.
    """
    return [Cell(label=f"f{axis}-{val}", rank=2)
            for axis in range(V) for val in range(D)]


def cube_volume() -> Cell:
    """Return the unique rank-3 cell spanning the whole cube."""
    return Cell(label="V", rank=3)


# =============================================================================
# INCIDENCE (precomputed per rank-k cell)
# =============================================================================

def _face_contains_vertex(face_label: str, vertex_idx: int) -> bool:
    """True iff vertex `vertex_idx` lies on face `face_label`."""
    axis_str, val_str = face_label[1:].split("-")
    axis = int(axis_str)
    val = int(val_str)
    return ((vertex_idx >> axis) & 1) == val


def _edge_endpoints(edge_label: str) -> tuple[int, int]:
    a_str, b_str = edge_label[1:].split("-")
    return int(a_str), int(b_str)


# =============================================================================
# CUBE COMBINATORIAL COMPLEX
# =============================================================================

@dataclass
class CubeComplex:
    """The 3-cube combinatorial complex with full rank 0..V structure.

    Fields:
        cells_by_rank : dict[rank -> list[Cell]]  — 0:vertices, 1:edges, 2:faces, 3:volume
        faces_of      : dict[Cell -> frozenset[Cell]]  — downward incidence to rank-(k-1)
        cofaces_of    : dict[Cell -> frozenset[Cell]]  — upward incidence to rank-(k+1)
        pinned        : set[Cell]  — regression subset; every sweep must re-verify these.
                        Monotone in practice (grow-only), though not enforced by the type.
    """
    cells_by_rank: dict[int, list[Cell]]
    faces_of: dict[Cell, frozenset[Cell]]
    cofaces_of: dict[Cell, frozenset[Cell]]
    pinned: set[Cell] = field(default_factory=set)

    @property
    def all_cells(self) -> list[Cell]:
        out: list[Cell] = []
        for r in sorted(self.cells_by_rank):
            out.extend(self.cells_by_rank[r])
        return out

    def cell_count(self) -> dict[int, int]:
        return {r: len(cs) for r, cs in self.cells_by_rank.items()}

    def cell_by_label(self, label: str) -> Optional[Cell]:
        for cs in self.cells_by_rank.values():
            for c in cs:
                if c.label == label:
                    return c
        return None


def build_cube_cc() -> CubeComplex:
    """Build the 3-cube combinatorial complex with full incidence tables."""
    verts = cube_vertices()
    edges = cube_edges()
    faces = cube_faces()
    volume = cube_volume()

    cells_by_rank: dict[int, list[Cell]] = {0: verts, 1: edges, 2: faces, 3: [volume]}

    faces_of: dict[Cell, frozenset[Cell]] = {}
    cofaces_of: dict[Cell, frozenset[Cell]] = {v: frozenset() for v in verts}
    for e in edges:
        cofaces_of[e] = frozenset()
    for f in faces:
        cofaces_of[f] = frozenset()
    cofaces_of[volume] = frozenset()

    # Rank 0 has no faces (by convention nothing below).
    for v in verts:
        faces_of[v] = frozenset()

    # Rank 1 (edges) -> two rank-0 faces each.
    edge_to_vs: dict[Cell, tuple[Cell, Cell]] = {}
    for e in edges:
        a, b = _edge_endpoints(e.label)
        va, vb = verts[a], verts[b]
        faces_of[e] = frozenset({va, vb})
        edge_to_vs[e] = (va, vb)
        cofaces_of[va] = cofaces_of[va] | {e}
        cofaces_of[vb] = cofaces_of[vb] | {e}

    # Rank 2 (faces) -> four rank-1 edges each.
    for f in faces:
        contained_verts = [i for i in range(Bott) if _face_contains_vertex(f.label, i)]
        contained_set = set(contained_verts)
        e_in_face: list[Cell] = []
        for e in edges:
            a, b = _edge_endpoints(e.label)
            if a in contained_set and b in contained_set:
                e_in_face.append(e)
        faces_of[f] = frozenset(e_in_face)
        for e in e_in_face:
            cofaces_of[e] = cofaces_of[e] | {f}

    # Rank 3 (volume) -> all six rank-2 faces.
    faces_of[volume] = frozenset(faces)
    for f in faces:
        cofaces_of[f] = cofaces_of[f] | {volume}

    return CubeComplex(cells_by_rank=cells_by_rank,
                       faces_of=faces_of,
                       cofaces_of=cofaces_of)


# =============================================================================
# CARRIER API — identity + axis-against relation per cell
# =============================================================================

def distinction_D(cell: Cell, cc: CubeComplex) -> tuple[str, frozenset[Cell], frozenset[Cell]]:
    """Distinction operator: D(cell) = (identity, faces, cofaces).

    identity : the cell's own label — reads as "what this cell IS".
    faces    : rank-(k-1) cells that are sub-cells — "what it CONTAINS".
    cofaces  : rank-(k+1) cells that contain it — "what CONTAINS it".

    Matches the signature of the hub's distinction operator; promoted to
    the full cube ranks 0..3.
    """
    return (cell.label, cc.faces_of.get(cell, frozenset()), cc.cofaces_of.get(cell, frozenset()))


def incidence_neighbors(cell: Cell, cc: CubeComplex) -> frozenset[Cell]:
    """Cells at the same rank as `cell` sharing at least one face with it.

    For a vertex: returns vertices at HD=1 (3 per vertex).
    For an edge: returns edges sharing an endpoint (each edge has 4 such siblings on the 3-cube).
    For a face: returns the 4 adjacent faces (sharing an edge).
    For the volume: empty (no siblings at rank 3).
    """
    if cell not in cc.faces_of:
        return frozenset()
    my_faces = cc.faces_of[cell]
    siblings = cc.cells_by_rank.get(cell.rank, [])
    out: set[Cell] = set()
    for other in siblings:
        if other == cell:
            continue
        if my_faces & cc.faces_of.get(other, frozenset()):
            out.add(other)
        # rank 0 has no faces; detect adjacency by being endpoints of a shared edge.
        elif cell.rank == 0:
            my_cofaces = cc.cofaces_of.get(cell, frozenset())
            other_cofaces = cc.cofaces_of.get(other, frozenset())
            if my_cofaces & other_cofaces:
                out.add(other)
    return frozenset(out)


def opposites(cell: Cell, cc: CubeComplex) -> Optional[Cell]:
    """Return the antipodal cell at the same rank, or None if none exists.

    Vertex v{i} opposes v{i XOR FANO}.
    Edge e{a}-{b} opposes e{a^FANO}-{b^FANO} (as a sorted label).
    Face f{axis}-{val} opposes f{axis}-{1-val}.
    Volume has no opposite (it's the unique top cell).
    """
    if cell.rank == 0:
        idx = int(cell.label[1:])
        return cc.cell_by_label(f"v{idx ^ FANO}")
    if cell.rank == 1:
        a, b = _edge_endpoints(cell.label)
        oa, ob = a ^ FANO, b ^ FANO
        if oa > ob:
            oa, ob = ob, oa
        return cc.cell_by_label(f"e{oa}-{ob}")
    if cell.rank == 2:
        axis_str, val_str = cell.label[1:].split("-")
        axis = int(axis_str)
        val = int(val_str)
        return cc.cell_by_label(f"f{axis}-{1 - val}")
    return None


def axis_against(a: Cell, b: Cell, cc: CubeComplex) -> dict:
    """Relation slots describing how `a` sits AS an axis against `b`.

    A cell is both identity (what it is) AND axis-against-other-cells. This
    function exposes the relational side of that duality.

    Returns a dict with:
        same_rank        : bool
        shared_faces     : frozenset of cells in the intersection of their faces
        incident_coface  : bool — is one a face of the other?
        are_opposite     : bool — antipodal at same rank?
        are_neighbors    : bool — share a face at same rank?
    """
    same_rank = (a.rank == b.rank)
    a_faces = cc.faces_of.get(a, frozenset())
    b_faces = cc.faces_of.get(b, frozenset())
    shared = a_faces & b_faces

    incident = (a in cc.faces_of.get(b, frozenset())) or (b in cc.faces_of.get(a, frozenset()))
    are_opp = False
    if same_rank:
        opp = opposites(a, cc)
        are_opp = (opp == b) if opp is not None else False

    are_nb = same_rank and bool(shared) and a != b
    return {
        "same_rank": same_rank,
        "shared_faces": shared,
        "incident_coface": incident,
        "are_opposite": are_opp,
        "are_neighbors": are_nb,
    }
