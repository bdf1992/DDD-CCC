"""
measure.py — base measurements over candidate SourceRecords.

Three layers (all run at import time, idempotently):
    intrinsic  — about the candidate itself (type, shape, fingerprint). Always runs.
    relational — candidate vs current cube state. Empty cube -> empty result.
    predictive — what happens if this candidate lands in a specific cell. Empty
                 cube -> neutral result.

Intrinsic is fully implemented. Relational and predictive carry the plumbing
but return empty/neutral until the cube accumulates placements. The
base-measurement pass is idempotent — run it every ingest, run it again after
each placement; results update monotonically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from s3.cubes.adapters.base import SourceRecord
from s3.cubes.extractors.metadata import normalize_metadata


# =============================================================================
# MEASUREMENT RESULT
# =============================================================================

@dataclass
class BaseMeasurement:
    """All base-measurement output for one candidate.

    intrinsic  : deterministic facts about the candidate alone.
    relational : comparisons against current cube state. Empty if cube is empty.
    predictive : forecasts per candidate cell. Empty if cube is empty.
    """
    source_id: str
    intrinsic: dict = field(default_factory=dict)
    relational: dict = field(default_factory=dict)
    predictive: dict = field(default_factory=dict)


# =============================================================================
# INTRINSIC CLASSIFIER — type / shape / fingerprint
# =============================================================================

# Type classifier — precedence order matters. First match wins.
_TYPE_RULES: tuple[tuple[str, re.Pattern], ...] = (
    ("test",   re.compile(r"(^|/)(test_|tests/|_test\.py$|conftest\.py$)")),
    ("spec",   re.compile(r"(^|/)(spec|specs|requirements)/|\.spec\.(md|py|js|ts)$")),
    ("config", re.compile(r"\.(ya?ml|toml|ini|cfg|json)$|(^|/)config(\.|/)")),
    ("data",   re.compile(r"\.(csv|tsv|jsonl|parquet|npz|npy)$|(^|/)data/")),
    ("code",   re.compile(r"\.(py|js|ts|jsx|tsx|c|h|cpp|hpp|cs|go|rs|java|kt|swift|rb|sh)$")),
    ("prose",  re.compile(r"\.(md|rst|txt)$")),
)


def classify_type(rec: SourceRecord) -> str:
    """Classify a SourceRecord into a type bucket.

    Buckets: code / prose / test / spec / config / data / source / datapoint /
    mapping / insight / gap / build / cycle / profile / mulch / term / idea /
    other.

    Greenfield rows use the primitive kind directly as the type. File-based
    sources match path rules.
    """
    # Greenfield primitives: use the primitive kind directly as the type.
    if rec.source_type.startswith("greenfield_"):
        return rec.source_type[len("greenfield_"):]

    # File-like: match the URI against rules.
    uri = rec.uri.replace("\\", "/")
    for name, pat in _TYPE_RULES:
        if pat.search(uri):
            return name
    return "other"


def structural_shape(rec: SourceRecord) -> dict:
    """Cheap structural summary of the body."""
    body = rec.body or ""
    lines = body.splitlines()
    non_blank = [ln for ln in lines if ln.strip()]
    headings = sum(1 for ln in lines if ln.lstrip().startswith("#"))
    code_fences = sum(1 for ln in lines if ln.lstrip().startswith("```"))
    out_refs = len(rec.outbound_refs)
    return {
        "lines_total": len(lines),
        "lines_nonblank": len(non_blank),
        "chars": len(body),
        "heading_count": headings,
        "code_fence_count": code_fences,
        "outbound_ref_count": out_refs,
    }


def intrinsic(rec: SourceRecord) -> dict:
    """Full intrinsic measurement bundle for a candidate."""
    canonical_md = normalize_metadata(rec)
    return {
        "type": classify_type(rec),
        "shape": structural_shape(rec),
        "fingerprint": rec.version_hash,
        "lineage": {
            "source_type": rec.source_type,
            "modified_at": canonical_md.get("modified_at"),
            "parent_refs": list(rec.parent_refs),
        },
        "tags": list(canonical_md.get("tags") or []),
        "canonical_metadata": canonical_md,
    }


# =============================================================================
# RELATIONAL — cube-aware (empty until cube has placements)
# =============================================================================

def relational(rec: SourceRecord, cube_state=None) -> dict:
    """Compare this candidate against the current cube state.

    Returns empty structure when the cube has no placements. Intended slots:
        nearest_cells      : list[(cell_label, similarity, reason)]
        incidence_candidates : list[cell_label] — cells this candidate could
                                 connect to via shared outbound_refs
        distance_to_vacuum : Optional[float] — nearest empty cell's structural
                                 distance from the candidate's best-fit region

    Populated when placements exist.
    """
    return {
        "nearest_cells": [],
        "incidence_candidates": [],
        "distance_to_vacuum": None,
    }


# =============================================================================
# PREDICTIVE — "what happens if this lands at cell X" (empty until cube exists)
# =============================================================================

def predictive(rec: SourceRecord, candidate_cells: Optional[list[str]] = None, cube_state=None) -> dict:
    """Forecast measurement deltas per candidate cell.

    Intended slots:
        per_cell : {cell_label -> {coverage_delta, frustration_delta,
                                   vacuum_delta, smoke_density_delta}}
    Returns empty dict when cube state is None/empty.
    """
    return {"per_cell": {}}


# =============================================================================
# PIPELINE — run all three on a batch
# =============================================================================

def measure(records: list[SourceRecord], cube_state=None) -> list[BaseMeasurement]:
    """Run intrinsic + relational + predictive over a batch of candidates.

    Relational and predictive return empty on an empty cube; intrinsic is always populated.
    """
    return [
        BaseMeasurement(
            source_id=rec.source_id,
            intrinsic=intrinsic(rec),
            relational=relational(rec, cube_state),
            predictive=predictive(rec, None, cube_state),
        )
        for rec in records
    ]
