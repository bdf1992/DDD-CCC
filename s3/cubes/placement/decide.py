"""
Placement decide — the atomic commit path for placement mutations.

Every decision is one of:
    ACCEPT <candidate, cell>       -> place candidate at cell
    REJECT <candidate, cell>       -> record rejection, no placement
    MODIFY <candidate, old, new>   -> move candidate from old cell to new cell
    UNPLACE <candidate, cell>      -> remove candidate from cell

All decisions flow through apply_decision(), which:
    1. validates the mutation against current IR state
    2. applies the mutation to a new IR instance (or in place)
    3. emits a Greenfield-shape signed datapoint (via emit module)
    4. appends the datapoint to ir.provenance

The decide step is the ONLY path that mutates placement state. Everything else
reads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class DecisionKind(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    MODIFY = "modify"
    UNPLACE = "unplace"


@dataclass
class PlacementDecision:
    """One user (or LLM) decision about a placement.

    kind        : accept / reject / modify / unplace
    source_id   : candidate being placed
    cell_label  : target cell for accept / reject; NEW cell for modify
    old_cell    : only for modify — the cell being vacated
    reasoning   : natural language justification (feeds datapoint evidence)
    actor       : identifier for who made the decision (user / agent / system)
    """
    kind: DecisionKind
    source_id: str
    cell_label: Optional[str] = None
    old_cell: Optional[str] = None
    reasoning: str = ""
    actor: str = "user"
    decided_at: str = ""

    def __post_init__(self):
        if not self.decided_at:
            self.decided_at = datetime.now(tz=timezone.utc).isoformat()


def _validate(decision: PlacementDecision, ir) -> list[str]:
    """Return a list of validation errors; empty means OK."""
    errs: list[str] = []

    if decision.kind == DecisionKind.MODIFY:
        if not decision.old_cell:
            errs.append("modify: old_cell is required")
        if not decision.cell_label:
            errs.append("modify: new cell_label is required")
    elif decision.kind in (DecisionKind.ACCEPT, DecisionKind.REJECT, DecisionKind.UNPLACE):
        if not decision.cell_label:
            errs.append(f"{decision.kind.value}: cell_label is required")

    if ir.cube is not None and decision.cell_label:
        if ir.cube.cell_by_label(decision.cell_label) is None:
            errs.append(f"cell_label '{decision.cell_label}' does not exist in the cube")
    if ir.cube is not None and decision.old_cell:
        if ir.cube.cell_by_label(decision.old_cell) is None:
            errs.append(f"old_cell '{decision.old_cell}' does not exist in the cube")

    if not any(c.source_id == decision.source_id for c in ir.candidates):
        errs.append(f"source_id '{decision.source_id}' not found in candidate pool")

    return errs


def apply_decision(
    ir,
    decision: PlacementDecision,
    prior_hash: Optional[str] = None,
) -> tuple[object, object]:
    """Apply a decision to the IR. Returns (new_ir, signed_datapoint).

    Mutates ir in place for efficiency (avoid deep copies per decision) and
    returns it as new_ir for API clarity. The signed datapoint is appended to
    ir.provenance.
    """
    errs = _validate(decision, ir)
    if errs:
        raise ValueError(f"placement decision invalid: {errs}")

    # Apply the mutation
    if decision.kind == DecisionKind.ACCEPT:
        ir.place(decision.cell_label, decision.source_id)
    elif decision.kind == DecisionKind.REJECT:
        pass  # no state change; rejection just records the decision
    elif decision.kind == DecisionKind.UNPLACE:
        ir.unplace(decision.cell_label, decision.source_id)
    elif decision.kind == DecisionKind.MODIFY:
        ir.unplace(decision.old_cell, decision.source_id)
        ir.place(decision.cell_label, decision.source_id)
    else:
        raise ValueError(f"unknown decision kind: {decision.kind}")

    # Emit signed datapoint
    from s3.cubes.placement.emit import emit_datapoint
    signed = emit_datapoint(ir, decision, prior_hash=prior_hash)
    ir.provenance.append(signed.to_dict())
    return ir, signed
