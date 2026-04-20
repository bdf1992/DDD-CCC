"""
Orientation-orbit initial sweep on the 3-cube combinatorial complex.

At ingest time, apply the cube's full orientation group
    B_3 = C_2 wr S_3 = hyperoctahedral group, order V! * D^V = 6 * 8 = 48
to a placement vector on the 8 F_2^3 vertices. Collect per-frame signals
and orbit aggregates.

The orbit decomposes signals into:
    - INVARIANT   : unchanged across all 48 rotations. This is the "real"
                    structural content of the placement — independent of our
                    arbitrary axis-labeling choices.
    - ANISOTROPIC : varies under rotation. This depends on how the user labeled
                    axes; orbit variance exposes where "which axis is which"
                    carries load-bearing information vs arbitrary assignment.

Load-bearing properties:
    - Hamming distance is rotation-invariant (the B_3 group preserves HD on F_2^3).
    - Therefore the Hamming histogram of pair distances between placed vertices
      is invariant, and the canonical V_4 gap signatures
      ({0,0,0,0} / {1,1,1,1} / {0,0,2,2} / {1,1,1,3}) are preserved (as sorted
      signatures).
    - Support count (number of non-zero vertices) is invariant.
    - Per-vertex values and unsorted axis energies are anisotropic — they
      permute across the orbit.

Baseline = orbit-integrated mean. Anisotropy = orbit variance per signal.

Acceptance (see earlier dev demo (removed)):
    1. Empty / uniform placements → ALL signals invariant (flat spectrum).
    2. Single-vertex placement → Hamming histogram + support count invariant;
       per-vertex values + axis energies anisotropic.
    3. For each HD class (0..V), sorted gap signatures match the canonical
       V_4 patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations, combinations
from pathlib import Path
from typing import Iterable, Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from primitives import V, D, FANO, Bott
from s3.cubes.element_algebra import (
    hamming_distance, get_layer, get_canonical_gap_signature, D2,
)


# =============================================================================
# ORIENTATION GROUP — B_3 = C_2 wr S_3 (order 48)
# =============================================================================

@dataclass(frozen=True)
class OrientationElement:
    """One element of the cube orientation group B_3 = C_2 wr S_3.

    axis_perm : permutation of (0, 1, 2) — relabels the V=3 coordinate axes.
    flip_mask : 3-bit mask in [0, D^V) = [0, 8); bit i flips axis i.

    Total group order: V! * D^V = 6 * 8 = 48.
    """
    axis_perm: tuple[int, ...]
    flip_mask: int

    def apply(self, vertex: int) -> int:
        """Apply this orientation to an F_2^V vertex index."""
        bits = [(vertex >> i) & 1 for i in range(V)]
        permuted = [bits[self.axis_perm[i]] for i in range(V)]
        flipped = [permuted[i] ^ ((self.flip_mask >> i) & 1) for i in range(V)]
        return sum(flipped[i] << i for i in range(V))

    def vertex_permutation(self) -> dict[int, int]:
        """Full {old_vertex -> new_vertex} permutation over 0..Bott-1."""
        return {v: self.apply(v) for v in range(Bott)}

    def label(self) -> str:
        return f"perm{''.join(str(x) for x in self.axis_perm)}_flip{self.flip_mask:03b}"


def cube_orientation_group() -> list[OrientationElement]:
    """Return the full 48-element cube orientation group B_3.

    Each element is a composition of an axis permutation (S_3, 6 elements) and
    an axis-flip mask (C_2^V, 8 elements). B_3 preserves the F_2^V cube graph
    and preserves Hamming distance.
    """
    return [
        OrientationElement(axis_perm=tuple(perm), flip_mask=flip)
        for perm in permutations(range(V))
        for flip in range(D ** V)
    ]


IDENTITY = OrientationElement(axis_perm=tuple(range(V)), flip_mask=0)


def orientation_preserves_hamming(orient: OrientationElement) -> bool:
    """Verify (by sampling) that an orientation preserves Hamming distance.
    Used as a structural invariant check; B_3 always satisfies it by construction."""
    for a in range(Bott):
        for b in range(a + 1, Bott):
            if hamming_distance(a, b) != hamming_distance(orient.apply(a), orient.apply(b)):
                return False
    return True


# =============================================================================
# PLACEMENT VECTOR + APPLY
# =============================================================================

def apply_orientation_to_vector(values: list[float], orient: OrientationElement) -> list[float]:
    """Rotate a length-Bott placement vector under an orientation.

    If values[v_old] = x, then after rotation, values[orient.apply(v_old)] = x.
    """
    if len(values) != Bott:
        raise ValueError(f"values must have {Bott} entries, got {len(values)}")
    new_values = [0.0] * Bott
    for old_v in range(Bott):
        new_v = orient.apply(old_v)
        new_values[new_v] = values[old_v]
    return new_values


# =============================================================================
# CANONICAL SIGNAL BUNDLE
# =============================================================================

@dataclass
class PlacementSignal:
    """Canonical signal bundle for one placement vector at one orientation.

    Fields split into invariant-under-B_3 (by construction) and anisotropic.

    Invariant:
        support_count     : number of vertices with |value| > tolerance
        support_set_size  : same as support_count (duplicate for clarity)
        hamming_histogram : dict {hd -> pair count} over placed vertices
        total_abs_energy  : sum |value| over placed vertices
        sorted_gap_signatures : sorted Counter of canonical V_4 gap signatures
                                across all placed pairs

    Anisotropic (vary under B_3 rotation):
        per_vertex_values : ordered list of values at vertex 0..Bott-1
        axis_energy       : per-V_4-axis layer-weighted energy (4 axes)
        top_vertex_index  : argmax vertex by absolute value (ties resolved low-first)
    """
    # Invariant
    support_count: int = 0
    hamming_histogram: dict[int, int] = field(default_factory=dict)
    total_abs_energy: float = 0.0
    sorted_gap_signature_histogram: dict[tuple, int] = field(default_factory=dict)

    # Anisotropic
    per_vertex_values: tuple[float, ...] = ()
    axis_energy: tuple[float, ...] = ()
    top_vertex_index: int = -1


_TOL = 1e-9


def compute_signal(values: list[float]) -> PlacementSignal:
    """Canonical signal bundle for a placement vector (one orientation)."""
    if len(values) != Bott:
        raise ValueError(f"values must have {Bott} entries, got {len(values)}")

    support = [i for i, v in enumerate(values) if abs(v) > _TOL]
    support_count = len(support)
    total_abs_energy = sum(abs(v) for v in values)

    # HD histogram over placed pairs
    hh: dict[int, int] = {}
    for a, b in combinations(support, 2):
        hd = hamming_distance(a, b)
        hh[hd] = hh.get(hd, 0) + 1

    # Canonical gap signature histogram: for each placed pair, the sorted V_4 gap
    # signature determined by HD. Rotation-invariant as a distribution.
    gap_hist: dict[tuple, int] = {}
    for a, b in combinations(support, 2):
        hd = hamming_distance(a, b)
        sig = tuple(sorted(get_canonical_gap_signature(hd)))
        gap_hist[sig] = gap_hist.get(sig, 0) + 1

    # Per-V_4-axis layer-weighted energy (VARIES under rotation)
    axis_energy = [0.0] * D2
    for p in range(D2):
        s = 0.0
        for v in range(Bott):
            if abs(values[v]) > _TOL:
                s += values[v] * int(get_layer(v, p))
        axis_energy[p] = s

    # Top vertex (VARIES under rotation)
    top_idx = -1
    top_abs = -1.0
    for v in range(Bott):
        a = abs(values[v])
        if a > top_abs:
            top_abs = a
            top_idx = v
    if top_abs <= _TOL:
        top_idx = -1

    return PlacementSignal(
        support_count=support_count,
        hamming_histogram=hh,
        total_abs_energy=total_abs_energy,
        sorted_gap_signature_histogram=gap_hist,
        per_vertex_values=tuple(values),
        axis_energy=tuple(axis_energy),
        top_vertex_index=top_idx,
    )


# =============================================================================
# ORBIT SWEEP + REPORT
# =============================================================================

@dataclass
class OrbitReport:
    """Full orientation-orbit sweep output.

    per_frame        : list[tuple[OrientationElement, PlacementSignal]] — 48 entries
    invariants       : dict of signal-name -> value (present if constant across all 48 frames)
    anisotropies     : dict of signal-name -> set-of-unique-values (present if it varies)
    baseline         : PlacementSignal at the identity orientation
    n_unique_frames  : count of distinct per-vertex-value tuples across the orbit
    """
    per_frame: list[tuple[OrientationElement, PlacementSignal]]
    invariants: dict[str, object]
    anisotropies: dict[str, list]
    baseline: PlacementSignal
    n_unique_frames: int

    @property
    def n_frames(self) -> int:
        return len(self.per_frame)

    @property
    def is_fully_invariant(self) -> bool:
        """True iff per-vertex-values is constant across all orientations."""
        return self.n_unique_frames == 1


def orbit_sweep(values: list[float]) -> OrbitReport:
    """Apply the full B_3 orientation group (48 elements) and collect signals.

    Returns an OrbitReport bundling per-frame signals + invariants + anisotropies.
    """
    group = cube_orientation_group()
    per_frame: list[tuple[OrientationElement, PlacementSignal]] = []
    for orient in group:
        rotated = apply_orientation_to_vector(values, orient)
        per_frame.append((orient, compute_signal(rotated)))

    # Invariant vs anisotropic detection
    invariants: dict[str, object] = {}
    anisotropies: dict[str, list] = {}

    # support_count (should be invariant by construction)
    sc_vals = {s.support_count for _, s in per_frame}
    if len(sc_vals) == 1:
        invariants["support_count"] = next(iter(sc_vals))
    else:
        anisotropies["support_count"] = sorted(sc_vals)

    # hamming_histogram (should be invariant by construction)
    hh_vals = {tuple(sorted(s.hamming_histogram.items())) for _, s in per_frame}
    if len(hh_vals) == 1:
        invariants["hamming_histogram"] = dict(next(iter(hh_vals)))
    else:
        anisotropies["hamming_histogram"] = [dict(t) for t in sorted(hh_vals)]

    # total_abs_energy (invariant)
    energy_vals = {round(s.total_abs_energy, 9) for _, s in per_frame}
    if len(energy_vals) == 1:
        invariants["total_abs_energy"] = next(iter(energy_vals))
    else:
        anisotropies["total_abs_energy"] = sorted(energy_vals)

    # sorted_gap_signature_histogram (invariant)
    gs_vals = {tuple(sorted(s.sorted_gap_signature_histogram.items())) for _, s in per_frame}
    if len(gs_vals) == 1:
        invariants["sorted_gap_signature_histogram"] = dict(next(iter(gs_vals)))
    else:
        anisotropies["sorted_gap_signature_histogram"] = [dict(t) for t in sorted(gs_vals)]

    # per_vertex_values (anisotropic unless placement is fully symmetric)
    pvv_vals = {s.per_vertex_values for _, s in per_frame}
    if len(pvv_vals) == 1:
        invariants["per_vertex_values"] = list(next(iter(pvv_vals)))
    else:
        anisotropies["per_vertex_values_unique_count"] = len(pvv_vals)

    # axis_energy (anisotropic — unsorted 4-tuple)
    ae_vals = {tuple(round(x, 9) for x in s.axis_energy) for _, s in per_frame}
    if len(ae_vals) == 1:
        invariants["axis_energy"] = list(next(iter(ae_vals)))
    else:
        anisotropies["axis_energy_unique_count"] = len(ae_vals)
        anisotropies["axis_energy_sample"] = sorted(ae_vals)[:3]

    # sorted axis_energy (invariant — permutation-equivalent rotation preserves multiset)
    sae_vals = {tuple(sorted(round(x, 9) for x in s.axis_energy)) for _, s in per_frame}
    if len(sae_vals) == 1:
        invariants["sorted_axis_energy"] = list(next(iter(sae_vals)))
    else:
        anisotropies["sorted_axis_energy"] = [list(t) for t in sorted(sae_vals)]

    # top_vertex_index (anisotropic — vertex permutes)
    tv_vals = {s.top_vertex_index for _, s in per_frame}
    if len(tv_vals) == 1:
        invariants["top_vertex_index"] = next(iter(tv_vals))
    else:
        anisotropies["top_vertex_index_orbit"] = sorted(tv_vals)

    # Baseline = identity-orientation frame
    baseline = per_frame[0][1]
    # Confirm: first frame is the identity (by construction of cube_orientation_group)
    assert per_frame[0][0] == IDENTITY, "first orbit element must be the identity"

    return OrbitReport(
        per_frame=per_frame,
        invariants=invariants,
        anisotropies=anisotropies,
        baseline=baseline,
        n_unique_frames=len(pvv_vals),
    )


# =============================================================================
# SUMMARY REPORT (for witness rendering)
# =============================================================================

def render_orbit_report(report: OrbitReport, label: str = "placement") -> list[str]:
    """Render an OrbitReport as human-readable text lines."""
    out: list[str] = []
    out.append(f"--- ORBIT SWEEP: {label} ---")
    out.append(f"  n_frames = {report.n_frames} (expected 48 = 3! * 2^3)")
    out.append(f"  n_unique_per_vertex_configurations = {report.n_unique_frames}")
    out.append(f"  fully_invariant = {report.is_fully_invariant}")
    out.append("  INVARIANTS (unchanged across all 48 rotations):")
    for k, v in sorted(report.invariants.items()):
        val_str = _format_value(v)
        out.append(f"    {k}: {val_str}")
    if report.anisotropies:
        out.append("  ANISOTROPIES (varies under rotation):")
        for k, v in sorted(report.anisotropies.items()):
            val_str = _format_value(v)
            out.append(f"    {k}: {val_str}")
    return out


def _format_value(v: object) -> str:
    if isinstance(v, list) and len(v) > 6:
        return f"[{len(v)} items: {v[:3]} ... {v[-1:]}]"
    return repr(v)
