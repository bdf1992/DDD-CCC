"""
Universal cube invariants that any axis proposal must satisfy.

Cube-structural, not semantic. The user's domain-specific meanings layer on
top, but every axis proposal is checked against these first.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from primitives import V


UNIVERSAL_INVARIANTS = (
    f"exactly_V_axes: proposal must declare {V} axes, no more, no fewer",
    "distinct_names: axis names must be distinct (case-sensitive)",
    "non_empty_bins: each axis must have >= 2 distinct bins with >= 1 candidate each",
    "non_overlapping_evidence: each axis's evidence must be derivable from a distinct signal source",
    "cross_rank_coverage: at least two cube ranks must be populated after placement",
)


class InvariantError(Exception):
    """Raised when an axis proposal violates a universal invariant."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_axis_proposal(proposal) -> list[str]:
    """Check an AxisProposal against the universal invariants.

    Returns a list of error strings; empty means valid. Does NOT raise —
    callers decide whether to raise `InvariantError` or present the errors
    to the user for refinement.
    """
    errs: list[str] = []
    axes = proposal.axes if hasattr(proposal, "axes") else list(proposal)

    if len(axes) != V:
        errs.append(f"exactly_V_axes: proposal has {len(axes)} axes, expected {V}")

    names = [a.name for a in axes]
    if len(set(names)) != len(names):
        errs.append(f"distinct_names: axis names must be unique, got {names}")

    for i, ax in enumerate(axes):
        bins = ax.bins if hasattr(ax, "bins") else []
        if len(bins) < 2:
            errs.append(
                f"non_empty_bins: axis {i} '{ax.name}' has {len(bins)} bins, expected >= 2"
            )
        populated = sum(1 for b in bins if b.get("count", 0) >= 1)
        if populated < min(2, len(bins)):
            errs.append(
                f"non_empty_bins: axis {i} '{ax.name}' has {populated} populated bins, expected >= 2"
            )

    sources = [ax.source_signal for ax in axes if hasattr(ax, "source_signal")]
    if len(set(sources)) < len(sources):
        errs.append(
            f"non_overlapping_evidence: axes draw from overlapping signals ({sources})"
        )

    return errs
