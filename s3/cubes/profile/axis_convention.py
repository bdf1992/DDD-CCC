"""
AxisConvention — committed, user-confirmed name<->slot binding.

Produced by the derive -> present -> refine protocol: the axis proposer
generates an AxisProposal, the skill presents it, the user refines, and the
result is committed as an AxisConvention. Changes to the convention are
first-class signed events (emit a provenance record).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from primitives import V
from s3.cubes.profile.invariants import validate_axis_proposal


@dataclass
class AxisConvention:
    """Committed axis convention. Lives inside KnowledgeIR.

    slot_to_name    : dict[int -> str] — canonical name per slot 0..V-1
    slot_to_signal  : dict[int -> str] — the source signal each axis reads
    confirmed_at    : ISO 8601 timestamp of user confirmation
    confirmed_by    : identifier for who confirmed (agent / user / system)
    evidence        : dict[slot -> evidence-record] — per-axis citation bundle
    """
    slot_to_name: dict[int, str] = field(default_factory=dict)
    slot_to_signal: dict[int, str] = field(default_factory=dict)
    confirmed_at: str = ""
    confirmed_by: str = ""
    evidence: dict[int, dict] = field(default_factory=dict)

    def __post_init__(self):
        if not self.confirmed_at:
            self.confirmed_at = datetime.now(tz=timezone.utc).isoformat()

    def is_complete(self) -> bool:
        return len(self.slot_to_name) == V and all(
            self.slot_to_name.get(s, "").strip() for s in range(V)
        )

    def to_dict(self) -> dict:
        return {
            "slot_to_name": {str(k): v for k, v in self.slot_to_name.items()},
            "slot_to_signal": {str(k): v for k, v in self.slot_to_signal.items()},
            "confirmed_at": self.confirmed_at,
            "confirmed_by": self.confirmed_by,
            "evidence": {str(k): v for k, v in self.evidence.items()},
        }


def commit_convention(
    proposal,
    confirmations: Optional[dict[int, str]] = None,
    confirmed_by: str = "user",
) -> AxisConvention:
    """Convert an AxisProposal into a committed AxisConvention.

    confirmations: optional dict mapping slot -> user-chosen-name (overrides
    the proposer's default). If None, the proposal's defaults are used verbatim.

    Validates the convention satisfies universal invariants before returning.
    """
    errs = validate_axis_proposal(proposal)
    if errs:
        raise ValueError(f"proposal fails universal invariants: {errs}")

    axes = proposal.axes
    slot_to_name = {}
    slot_to_signal = {}
    evidence = {}
    for ax in axes:
        name = (confirmations or {}).get(ax.slot) or ax.name
        slot_to_name[ax.slot] = name
        slot_to_signal[ax.slot] = ax.source_signal
        evidence[ax.slot] = {
            "description": ax.description,
            "source_signal": ax.source_signal,
            "bins": ax.bins,
            "entropy": ax.entropy,
        }
    return AxisConvention(
        slot_to_name=slot_to_name,
        slot_to_signal=slot_to_signal,
        confirmed_by=confirmed_by,
        evidence=evidence,
    )
