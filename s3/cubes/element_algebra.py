"""
Element algebra over F_2^3 — Hamming distance, V_4 axis projection,
HdMatch classification, axis-gap decomposition, meta-spectrum aggregation.

All constants come from primitives.py. No Unity dependency.

Key identity: each axis p in {0,1,2,3} projects every element x to
    layer L_p(x) = popcount(x XOR p)
Lower vertices {0..3} always use layers 0-2 (broadly resonant).
Upper vertices {4..7} always use layers 1-3 (narrowly specialized).
Opposition pairs (x, x XOR 7) swap Ground<->Apex and Near<->Far on every axis.

The four axes are body-diagonals of the cube: Existence (P0), Energy (P1),
Substance (P2), Structure (P3). D2 = D*D = 4 counts them.
"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from primitives import V, D, FANO, Bott

# Derived count constants
D2 = D * D          # = 4. Count of V_4 axes.
D4 = D2 * D2        # = 16. Meta spectrum bin count (4 axes * 4 layers).


class AxisLayer(IntEnum):
    """Layer on an axis p. Ground=defines axis, Apex=opposite body-diagonal."""
    Ground = 0   # HD=0 from p: p itself
    Near   = 1   # HD=1 from p: resonates
    Far    = 2   # HD=2 from p: distant
    Apex   = 3   # HD=3 from p: antipode


class Axis(IntEnum):
    """The four body-diagonal axes of the F_2^3 cube. Axis p = XOR with p."""
    Existence = 0   # P0: Void <-> Aether
    Energy    = 1   # P1: Fire <-> Water
    Substance = 2   # P2: Earth <-> Air
    Structure = 3   # P3: Order <-> Chaos


class HdMatch(IntEnum):
    """Hamming-distance based match classification for pairs of vertices."""
    Mirror = 0   # HD=0: same element
    Reso   = 1   # HD=1: cube-adjacent
    Fric   = 2   # HD=2: cube-distant
    Clash  = 3   # HD=3: opposition


# =============================================================================
# HAMMING DISTANCE
# =============================================================================

def popcount(x: int) -> int:
    """Popcount for 3-bit values (0-7). Masks to FANO bits first."""
    x &= FANO
    return ((x >> 2) & 1) + ((x >> 1) & 1) + (x & 1)


def hamming_distance(a: int, b: int) -> int:
    """Hamming distance between two F_2^3 elements (returns 0..3)."""
    return popcount((a ^ b) & FANO)


# =============================================================================
# V_4 AXIS PROJECTION
# =============================================================================

def get_layer(element: int, axis: int) -> AxisLayer:
    """Layer L_p(x) = popcount(x XOR p). Returns AxisLayer 0..3."""
    return AxisLayer(popcount((element ^ axis) & FANO))


def get_axis_profile(element: int) -> list[AxisLayer]:
    """Full 4-axis profile for one element: [L_0, L_1, L_2, L_3]."""
    return [get_layer(element, p) for p in range(D2)]


# =============================================================================
# MATCH OUTCOMES (HD-BASED)
# =============================================================================

def get_hd_match(a: int, b: int) -> HdMatch:
    """HD-based match between two elements."""
    return HdMatch(hamming_distance(a, b))


def get_scalar_multiplier(match: HdMatch) -> float:
    """Match multiplier: Mirror=1.0, Reso=1.5, Fric=1.0, Clash=0.5."""
    return {HdMatch.Mirror: 1.0, HdMatch.Reso: 1.5,
            HdMatch.Fric: 1.0, HdMatch.Clash: 0.5}[match]


def get_additive_score(match: HdMatch) -> int:
    """Additive score: Mirror=0, Reso=+1, Fric=0, Clash=-1."""
    return {HdMatch.Mirror: 0, HdMatch.Reso: 1,
            HdMatch.Fric: 0, HdMatch.Clash: -1}[match]


# =============================================================================
# AXIS-GAP DECOMPOSITION
# =============================================================================

def get_axis_gaps(a: int, b: int) -> list[int]:
    """Per-axis layer gaps: delta_p = |L_p(a) - L_p(b)|. Returns 4 ints.

    Depends only on HD(a,b). Canonical forms (sorted):
        HD=0 -> [0,0,0,0]  Mirror
        HD=1 -> [1,1,1,1]  Reso
        HD=2 -> [0,0,2,2]  Fric
        HD=3 -> [1,1,1,3]  Clash
    (The actual axis assignment varies by pair; gaps above are the unsorted form.)
    """
    gaps = []
    for p in range(D2):
        la = popcount((a ^ p) & FANO)
        lb = popcount((b ^ p) & FANO)
        gaps.append(abs(la - lb))
    return gaps


def get_canonical_gap_signature(hd: int) -> list[int]:
    """Sorted gap signature determined entirely by HD value."""
    return {0: [0, 0, 0, 0],
            1: [1, 1, 1, 1],
            2: [0, 0, 2, 2],
            3: [1, 1, 1, 3]}.get(hd, [0, 0, 0, 0])


# =============================================================================
# META SPECTRUM (16-BIN AGGREGATION)
# =============================================================================

def compute_meta_spectrum(signature: list[float]) -> list[float]:
    """Compute meta spectrum from a Wave-shape signature (length Bott).

    Returns D4 = 16 bins = 4 axes * 4 layers. Index = axis * 4 + layer.
        S_p[Ground] = sig[p]
        S_p[Near]   = sig[p^1] + sig[p^2] + sig[p^4]
        S_p[Far]    = sig[p^3] + sig[p^5] + sig[p^6]
        S_p[Apex]   = sig[p^7]
    """
    if len(signature) != Bott:
        raise ValueError(f"signature must have {Bott} entries, got {len(signature)}")
    spectrum = [0.0] * D4
    for p in range(D2):
        spectrum[p * 4 + 0] = signature[p]
        spectrum[p * 4 + 1] = signature[p ^ 1] + signature[p ^ 2] + signature[p ^ 4]
        spectrum[p * 4 + 2] = signature[p ^ 3] + signature[p ^ 5] + signature[p ^ 6]
        spectrum[p * 4 + 3] = signature[p ^ 7]
    return spectrum


# =============================================================================
# OPPOSITION
# =============================================================================

def get_opposition(element: int) -> int:
    """Antipodal element: x XOR FANO (flip all 3 bits)."""
    return (element ^ FANO) & FANO


def are_opposed(a: int, b: int) -> bool:
    """True iff the pair sits on a body-diagonal (HD = V = 3)."""
    return hamming_distance(a, b) == V


# =============================================================================
# ELEMENT CLASSIFICATION
# =============================================================================

def is_lower(element: int) -> bool:
    """Lower half {0..3} — broad resonators, layers 0..2."""
    return element < D2


def is_upper(element: int) -> bool:
    """Upper half {4..7} — narrow specialists, layers 1..3."""
    return element >= D2
