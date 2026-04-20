"""
KnowledgeIR — the canonical in-memory knowledge graph of a cube run.

Bundles: candidates (SourceRecord set) + placements (cell_label -> source_ids)
+ datum_instances (emitted DatumInstance set) + measurements (metric plugin
outputs) + cube (CubeComplex structural context) + axis_convention (name<->slot
binding) + provenance (signed datapoint chain metadata).

Deterministically constructible from the signed datapoint stream: cube state
IS a reduction of the stream, and the KnowledgeIR is that reduction in memory.
Consumed by the dashboard + (eventually) transducers.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if TYPE_CHECKING:
    from s3.cubes.adapters.base import SourceRecord
    from s3.cubes.combinatorial_complex import CubeComplex
    from s3.cubes.datums.base import DatumInstance


@dataclass
class KnowledgeIRSnapshot:
    """Per-metric / per-sweep measurement snapshot held inside KnowledgeIR.

    name         : plugin or sweep identifier
    payload      : structured measurement output (dict of cells / scalars / lists)
    observed_at  : ISO 8601 timestamp
    """
    name: str
    payload: dict
    observed_at: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(tz=timezone.utc).isoformat()


@dataclass
class KnowledgeIR:
    """The canonical in-memory reduction of the signed datapoint stream.

    candidates       : list[SourceRecord] — every candidate the cube has seen
    placements       : dict[cell_label -> list[source_id]] — which records sit on which cells
    datum_instances  : list[DatumInstance] — emitted claims with evidence
    measurements     : list[KnowledgeIRSnapshot] — metric plugin outputs + sweep results
    cube             : CubeComplex — structural context (ranks / incidence / pinned)
    axis_convention  : dict[int, str] — slot index -> user-visible axis name
    provenance       : list[dict] — signed datapoint chain (Greenfield-shape)
    observed_at      : when this IR was assembled
    """
    candidates: list = field(default_factory=list)
    placements: dict[str, list[str]] = field(default_factory=dict)
    datum_instances: list = field(default_factory=list)
    measurements: list[KnowledgeIRSnapshot] = field(default_factory=list)
    cube: Optional["CubeComplex"] = None
    axis_convention: dict[int, str] = field(default_factory=dict)
    provenance: list[dict] = field(default_factory=list)
    observed_at: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(tz=timezone.utc).isoformat()

    # --- convenience views ---

    def candidates_by_id(self) -> dict:
        return {c.source_id: c for c in self.candidates}

    def candidates_at_cell(self, cell_label: str) -> list:
        ids = set(self.placements.get(cell_label, ()))
        return [c for c in self.candidates if c.source_id in ids]

    def cells_with_placements(self) -> set[str]:
        return {cell for cell, ids in self.placements.items() if ids}

    def placement_count(self) -> int:
        return sum(len(v) for v in self.placements.values())

    def axis_name(self, slot: int, default: Optional[str] = None) -> str:
        return self.axis_convention.get(slot, default or f"axis_{slot}")

    # --- mutation ---

    def place(self, cell_label: str, source_id: str) -> None:
        """Add a (cell, source) placement. Idempotent."""
        lst = self.placements.setdefault(cell_label, [])
        if source_id not in lst:
            lst.append(source_id)

    def unplace(self, cell_label: str, source_id: str) -> bool:
        """Remove a placement. Returns True iff it was present."""
        lst = self.placements.get(cell_label, [])
        if source_id in lst:
            lst.remove(source_id)
            if not lst:
                del self.placements[cell_label]
            return True
        return False

    def perturb(self, cell_label: str, new_source_ids: list[str]) -> "KnowledgeIR":
        """Return a variant IR with `cell_label` replaced by `new_source_ids`.

        Mutation operator for measurement-blindness detection. Does not
        mutate in place — returns a new IR with a copied placement map. Metric
        plugins run on the variant to detect whether any metric's output
        changed. Unchanged metrics indicate a blind region in the measurement
        suite for this cell.
        """
        new_placements = {k: list(v) for k, v in self.placements.items()}
        if new_source_ids:
            new_placements[cell_label] = list(new_source_ids)
        else:
            new_placements.pop(cell_label, None)
        return KnowledgeIR(
            candidates=list(self.candidates),
            placements=new_placements,
            datum_instances=list(self.datum_instances),
            measurements=[],  # measurements recompute on the variant
            cube=self.cube,
            axis_convention=dict(self.axis_convention),
            provenance=list(self.provenance),
        )

    # --- provenance + fingerprinting ---

    def fingerprint(self) -> str:
        """Stable sha256 fingerprint of the IR's placement graph.

        Used by the transducer layer for round-trip diffs. Only
        includes canonical content: sorted candidate ids, sorted placements,
        axis convention. Excludes timestamps.
        """
        h = hashlib.sha256()
        h.update(b"KnowledgeIR/v0\n")
        h.update(b"candidates:")
        for cid in sorted(c.source_id for c in self.candidates):
            h.update(cid.encode("utf-8") + b"\n")
        h.update(b"placements:")
        for cell in sorted(self.placements):
            h.update(cell.encode("utf-8") + b":")
            for sid in sorted(self.placements[cell]):
                h.update(sid.encode("utf-8") + b",")
            h.update(b"\n")
        h.update(b"axis_convention:")
        for slot in sorted(self.axis_convention):
            h.update(f"{slot}:{self.axis_convention[slot]}\n".encode("utf-8"))
        return "sha256:" + h.hexdigest()

    def to_summary(self) -> dict:
        """Compact summary (no bodies) suitable for witness artifacts."""
        return {
            "n_candidates": len(self.candidates),
            "n_placed_cells": len(self.placements),
            "n_placements": self.placement_count(),
            "n_datum_instances": len(self.datum_instances),
            "n_measurements": len(self.measurements),
            "axis_convention": dict(self.axis_convention),
            "fingerprint": self.fingerprint(),
            "observed_at": self.observed_at,
        }


def empty_ir(cube=None) -> KnowledgeIR:
    """Construct an empty KnowledgeIR anchored at the given CubeComplex (or None)."""
    return KnowledgeIR(cube=cube)
