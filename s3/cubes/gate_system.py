"""
Gate system — element relationship engine.

Layer 1 (Classification): 6 gate types derived from F_2^3 geometry + Fano lines.
Layer 2 (Dynamics): ease (resolution speed) + sign preference (direction) per gate.

Derivation:
    1. Compute HD = Hamming distance on F_2^3 (popcount of XOR)
    2. Check Fano line membership (7 projective lines through 7 non-zero vertices)
    3. For HD=2 pairs sharing a Fano line, check the third line element:
       if HD(self, third) = 3 -> balanced; else -> friction

All constants from primitives.py. Ease values forced by V=3, D=2:
    ease(ally)     = D^2 / V = 4/3
    ease(balanced) = 1/D     = 1/2
    ease(friction) = 1/D^2   = 1/4
    ease(opp)      = 1/(D*V) = 1/6
"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from primitives import V, D, FANO, Bott
from s3.cubes.element_algebra import hamming_distance, D2


class GateType(IntEnum):
    """The 6 gate types between any pair of vertices.

    Ordered by ease (fastest resolution first).
    """
    Self     = 0   # HD=0
    Ally     = 1   # HD=1, shared Fano line
    Balanced = 2   # Void's view, or HD=2 with opp-third on shared Fano line
    Friction = 3   # HD=2, shared Fano line, third is NOT opposition
    Opp      = 4   # HD=3 (body-diagonal)
    Blind    = 5   # no Fano line between them


class GateSign(IntEnum):
    """Sign preference: what direction of delta does this gate want?"""
    Positive = 1    # +delta is reward (strengthen)
    Neutral  = 0    # magnitude matters, direction doesn't
    Negative = -1   # -delta is reward (weaken)


# =============================================================================
# FANO LINES (7 projective lines through F_2^3 \ {0})
# =============================================================================
# Each line has 3 vertices XOR-ing to 0. The standard enumeration.

FANO_LINES: tuple[tuple[int, int, int], ...] = (
    (1, 2, 3),   # Fire,  Earth, Order
    (1, 4, 5),   # Fire,  Chaos, Air
    (1, 6, 7),   # Fire,  Water, Aether
    (2, 4, 6),   # Earth, Chaos, Water
    (2, 5, 7),   # Earth, Air,   Aether
    (3, 4, 7),   # Order, Chaos, Aether
    (3, 5, 6),   # Order, Air,   Water
)

# Precomputed: for each vertex v in 0..7, which Fano lines contain v (by index 0..6).
_FANO_MEMBERSHIP: tuple[tuple[int, ...], ...] = tuple(
    tuple(li for li, line in enumerate(FANO_LINES) if v in line)
    for v in range(Bott)
)


def _find_shared_line(a: int, b: int) -> int:
    """Return Fano-line index shared by a and b, or -1 if none."""
    for li in _FANO_MEMBERSHIP[a]:
        if b in FANO_LINES[li]:
            return li
    return -1


def _classify_gate(a: int, b: int) -> GateType:
    """Derive the GateType from geometry."""
    if a == b:
        return GateType.Self
    if (a ^ b) == FANO:
        return GateType.Opp

    hd = hamming_distance(a, b)

    # Void (vertex 0) is not on any Fano line — sees adjacency as balanced, far as blind.
    if a == 0:
        return GateType.Balanced if hd <= 1 else GateType.Blind

    shared = _find_shared_line(a, b)
    if shared < 0:
        return GateType.Blind

    if hd == 1:
        return GateType.Ally

    # HD=2, shared line present: read the third line element.
    line = FANO_LINES[shared]
    third = next(x for x in line if x != a and x != b)
    if hamming_distance(a, third) == V:
        return GateType.Balanced
    return GateType.Friction


def build_gate_table() -> list[list[GateType]]:
    """Build the full Bott x Bott gate table from geometry. Returns nested list."""
    return [[_classify_gate(a, b) for b in range(Bott)] for a in range(Bott)]


# Module-level precomputed table.
GATE_TABLE: list[list[GateType]] = build_gate_table()


# =============================================================================
# LAYER 2: DYNAMICS (ease + sign + resolution)
# =============================================================================

def ease(gate: GateType) -> float:
    """Resolution ease per gate. Higher = faster. All forced by V=3, D=2."""
    return {
        GateType.Self:     1.0,
        GateType.Ally:     D2 / V,              # 4/3
        GateType.Balanced: 1.0 / D,             # 1/2
        GateType.Friction: 1.0 / D2,            # 1/4
        GateType.Opp:      1.0 / (D * V),       # 1/6
        GateType.Blind:    0.0,
    }[gate]


def sign_preference(gate: GateType) -> GateSign:
    """Sign preference for each gate."""
    return {
        GateType.Self:     GateSign.Positive,
        GateType.Ally:     GateSign.Positive,
        GateType.Balanced: GateSign.Neutral,
        GateType.Friction: GateSign.Negative,
        GateType.Opp:      GateSign.Negative,
        GateType.Blind:    GateSign.Neutral,
    }[gate]


def resolve_delta(gate: GateType, delta: float, t: float) -> float:
    """Resolve a delta through a gate at time t. Clamped to [0, |delta|]."""
    e = ease(gate)
    if e <= 0.0:
        return 0.0
    return delta * min(t * e, 1.0)


def residual(gate: GateType, delta: float) -> float:
    """Unresolved delta at t=1. Carried to the next turn."""
    e = ease(gate)
    if e >= 1.0:
        return 0.0
    return delta * (1.0 - e)


# =============================================================================
# CONVENIENCE API
# =============================================================================

def get_gate(a: int, b: int) -> GateType:
    """Gate from vertex a toward vertex b (masks to FANO bits)."""
    return GATE_TABLE[a & FANO][b & FANO]


def get_gate_string(element: int) -> list[GateType]:
    """Full 8-gate string for an element (one gate per target)."""
    return [GATE_TABLE[element & FANO][b] for b in range(Bott)]


def gate_string_to_values(element: int) -> list[Optional[float]]:
    """Canonical gate-string preset as [-1, +1] floats (None for Blind).

    Self=1.0, Ally=0.5, Balanced=0.0, Friction=-0.5, Opp=-1.0, Blind=None.
    """
    mapping = {
        GateType.Self:     1.0,
        GateType.Ally:     0.5,
        GateType.Balanced: 0.0,
        GateType.Friction: -0.5,
        GateType.Opp:      -1.0,
        GateType.Blind:    None,
    }
    return [mapping[GATE_TABLE[element & FANO][b]] for b in range(Bott)]


def share_fano_line(a: int, b: int) -> bool:
    """True iff a, b share a Fano line. Void (0) is on no line."""
    if a == 0 or b == 0:
        return False
    return _find_shared_line(a, b) >= 0


def get_fano_lines_of(element: int) -> list[tuple[int, int, int]]:
    """All Fano lines containing this element. Empty for Void."""
    if element == 0:
        return []
    return [FANO_LINES[li] for li in _FANO_MEMBERSHIP[element]]
