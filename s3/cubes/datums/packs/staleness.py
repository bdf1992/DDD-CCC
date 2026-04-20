"""
StalenessDatumPack — first reference pack.

Three primitive datums, each schema-complete per the YAML contract,
each with a Python composer that reads candidates + placements + cube state
and emits DatumInstances.

    doc_older_than_code        — a doc cell is staler than incident code it references
    spec_never_implemented     — a spec cell has no adjacent code cell in the cube
    test_older_than_code_under_test — a test is staler than the code it tests

All three tier=primitive. They assume the cube has placements; with an empty
cube they return no instances (not an error — just nothing to say yet).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from s3.cubes.datums.base import (
    Datum, DatumFamily, DatumTier,
    DatumContext, DatumInstance,
    DatumRegistry,
)


# =============================================================================
# HELPERS
# =============================================================================

def _modified_at(rec) -> Optional[datetime]:
    """Pull the canonical modified_at from a record's metadata. Returns a tz-aware datetime or None."""
    md = rec.metadata or {}
    ts = md.get("modified_at")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _record_type(rec) -> str:
    from s3.cubes.measure import classify_type
    return classify_type(rec)


def _inverted_placements(context: DatumContext) -> dict[str, list[str]]:
    """source_id -> list of cell_labels it's placed at."""
    out: dict[str, list[str]] = {}
    for cell_label, ids in context.placements.items():
        for sid in ids:
            out.setdefault(sid, []).append(cell_label)
    return out


def _referenced_records(rec, by_id: dict) -> list:
    """Records referenced by `rec.outbound_refs` that exist in the candidate pool.

    Matches by source_id direct equality, then by URI tail / title contains.
    Minimal — smarter link resolution lands with extractors.links.
    """
    out = []
    seen = set()
    for ref in rec.outbound_refs:
        # direct id match
        if ref in by_id and ref not in seen:
            out.append(by_id[ref]); seen.add(ref); continue
        # fallback: path tail / title match
        ref_tail = Path(str(ref)).name.lower()
        for sid, other in by_id.items():
            if sid in seen:
                continue
            uri_tail = Path(other.uri).name.lower()
            if ref_tail and (ref_tail == uri_tail or (other.title and other.title.lower() == str(ref).lower())):
                out.append(other); seen.add(sid); break
    return out


# =============================================================================
# doc_older_than_code
# =============================================================================

def _compute_doc_older_than_code(
    datum: Datum, context: DatumContext,
    threshold_days: int = 30,
) -> list[DatumInstance]:
    by_id = context.candidates_by_id()
    inv = _inverted_placements(context)
    out: list[DatumInstance] = []

    for doc in context.candidates:
        if _record_type(doc) != "prose":
            continue
        doc_t = _modified_at(doc)
        if doc_t is None:
            continue

        for target in _referenced_records(doc, by_id):
            if _record_type(target) != "code":
                continue
            code_t = _modified_at(target)
            if code_t is None:
                continue

            delta = code_t - doc_t
            if delta < timedelta(days=threshold_days):
                continue

            delta_days = int(delta.total_seconds() / 86400)
            severity = "high" if delta_days > 180 else ("medium" if delta_days > 60 else "low")
            claim = (
                f"Doc '{doc.title or doc.uri}' was last modified {doc_t.date().isoformat()}, "
                f"but the code it references '{target.title or target.uri}' was updated "
                f"{code_t.date().isoformat()} ({delta_days} days newer)."
            )
            out.append(DatumInstance(
                datum_qualified_name=datum.qualified_name,
                severity=severity,
                claim=claim,
                evidence={
                    "doc_source_id": doc.source_id,
                    "doc_modified_at": doc_t.isoformat(),
                    "code_source_id": target.source_id,
                    "code_modified_at": code_t.isoformat(),
                    "delta_days": delta_days,
                    "threshold_days": threshold_days,
                },
                recommended_action=(
                    f"Review and update '{doc.title or doc.uri}' to reflect recent changes in "
                    f"'{target.title or target.uri}', or confirm the doc is intentionally historical."
                ),
                cell_refs=list(set(inv.get(doc.source_id, []) + inv.get(target.source_id, []))),
                source_refs=[doc.source_id, target.source_id],
            ))
    return out


DOC_OLDER_THAN_CODE = Datum(
    name="doc_older_than_code",
    family=DatumFamily.STALENESS,
    tier=DatumTier.PRIMITIVE,
    description="A documentation cell predates the code cell it references by more than the threshold.",
    inputs={
        "storage_signals": ["file_modified_at", "source_type"],
        "interaction_signals": [],
        "cube_signals": ["cell_rank", "incident_cells"],
        "text_signals": ["outbound_refs"],
    },
    semantic_check={
        "claim": "This documentation predates the code it links to by more than the staleness threshold.",
        "must_have": ["cited_code_target", "modified_at_both_sides", "age_threshold"],
    },
    syntactic_check={
        "required_fields": ["doc_source_id", "code_source_id", "delta_days"],
    },
    output={
        "severity": "medium",
        "claim": "Doc {doc_source_id} is {delta_days} days older than code {code_source_id}.",
        "evidence": {"doc_modified_at": "ISO8601", "code_modified_at": "ISO8601", "delta_days": "int"},
        "recommended_action": "Review and update the documentation, or confirm it is intentionally historical.",
    },
    examples={
        "positive": {"doc": "docs/guide.md (2024-01-01)", "code": "src/main.py (2026-04-01)", "delta_days": 821},
        "negative": {"doc": "docs/guide.md (2026-04-15)", "code": "src/main.py (2026-04-01)", "delta_days": -14},
    },
    failure_mode=(
        "Overfires on docs intentionally kept as historical archive. "
        "Underfires when a doc has no outbound link to its code. "
        "Does not fire if the doc references code outside the candidate pool."
    ),
    composer=_compute_doc_older_than_code,
)


# =============================================================================
# spec_never_implemented
# =============================================================================

def _compute_spec_never_implemented(
    datum: Datum, context: DatumContext,
) -> list[DatumInstance]:
    by_id = context.candidates_by_id()
    inv = _inverted_placements(context)
    out: list[DatumInstance] = []

    # Every spec candidate: does any code candidate cite or share a cell with it?
    for spec in context.candidates:
        if _record_type(spec) != "spec":
            continue
        spec_cells = inv.get(spec.source_id, [])

        # 1) Check direct references: does any code record reference this spec by title/id?
        cited = False
        for other in context.candidates:
            if _record_type(other) != "code":
                continue
            if spec.source_id in other.outbound_refs:
                cited = True
                break
            if spec.title and spec.title in other.outbound_refs:
                cited = True
                break

        # 2) Check cell co-placement: does a code record sit on any of spec's cells?
        if not cited and spec_cells:
            for cell in spec_cells:
                for sid in context.placements.get(cell, []):
                    if sid == spec.source_id:
                        continue
                    other = by_id.get(sid)
                    if other and _record_type(other) == "code":
                        cited = True
                        break
                if cited:
                    break

        if cited:
            continue

        out.append(DatumInstance(
            datum_qualified_name=datum.qualified_name,
            severity="high",
            claim=(
                f"Spec '{spec.title or spec.uri}' has no implementing code in the current candidate pool "
                "— neither cited by any code nor co-placed on any spec cell."
            ),
            evidence={
                "spec_source_id": spec.source_id,
                "spec_cells": spec_cells,
                "code_candidate_count": sum(1 for r in context.candidates if _record_type(r) == "code"),
            },
            recommended_action=(
                f"Either author an implementing module for '{spec.title or spec.uri}' "
                "or mark the spec as aspirational."
            ),
            cell_refs=spec_cells,
            source_refs=[spec.source_id],
        ))
    return out


SPEC_NEVER_IMPLEMENTED = Datum(
    name="spec_never_implemented",
    family=DatumFamily.STALENESS,
    tier=DatumTier.PRIMITIVE,
    description="A spec cell has no implementing code cell adjacent to it in the cube.",
    inputs={
        "storage_signals": ["source_type", "path_pattern"],
        "interaction_signals": [],
        "cube_signals": ["cell_rank", "incident_cells", "vacuum_score"],
        "text_signals": ["outbound_refs"],
    },
    semantic_check={
        "claim": "This spec describes behavior with no implementation mapped into the cube.",
        "must_have": ["spec_identified", "absence_of_code_in_region"],
    },
    syntactic_check={
        "required_fields": ["spec_source_id", "spec_cells", "code_candidate_count"],
    },
    output={
        "severity": "high",
        "claim": "Spec {spec_source_id} has no implementing code in the candidate pool.",
        "evidence": {"spec_cells": "list[str]", "code_candidate_count": "int"},
        "recommended_action": "Author the implementation or mark the spec aspirational.",
    },
    examples={
        "positive": {"spec": "specs/auth.md with 0 code references", "cells": ["f0-1"]},
        "negative": {"spec": "specs/auth.md cited by src/auth.py", "cells": ["f0-1"]},
    },
    failure_mode=(
        "Overfires when implementing code lives outside the candidate pool (e.g., a separate repo). "
        "Underfires when spec and code share a cell but the code is actually a stub."
    ),
    composer=_compute_spec_never_implemented,
)


# =============================================================================
# test_older_than_code_under_test
# =============================================================================

_TEST_PATH_RE = re.compile(r"(^|/)(test_|tests/|_test\.py$|conftest\.py$)")


def _paired_module_for_test(test_rec, by_id) -> Optional[object]:
    """Given a test record, find the module it tests via path convention.

    Looks for `test_<module>.py` -> `<module>.py`, or `tests/<dir>/<name>_test.py`
    -> `<dir>/<name>.py`. Heuristic; smarter pairing lands later.
    """
    uri = test_rec.uri.replace("\\", "/")
    name = Path(uri).name
    # test_foo.py -> foo.py
    if name.startswith("test_") and name.endswith(".py"):
        target_name = name[5:]
    elif name.endswith("_test.py"):
        target_name = name[:-8] + ".py"
    else:
        return None
    for other in by_id.values():
        other_uri = other.uri.replace("\\", "/")
        if Path(other_uri).name == target_name and _record_type(other) == "code":
            return other
    return None


def _compute_test_older_than_code(
    datum: Datum, context: DatumContext,
    threshold_days: int = 14,
) -> list[DatumInstance]:
    by_id = context.candidates_by_id()
    inv = _inverted_placements(context)
    out: list[DatumInstance] = []

    for test in context.candidates:
        if _record_type(test) != "test":
            continue
        test_t = _modified_at(test)
        if test_t is None:
            continue
        target = _paired_module_for_test(test, by_id)
        if target is None:
            continue
        target_t = _modified_at(target)
        if target_t is None:
            continue

        delta = target_t - test_t
        if delta < timedelta(days=threshold_days):
            continue

        delta_days = int(delta.total_seconds() / 86400)
        severity = "high" if delta_days > 60 else ("medium" if delta_days > 21 else "low")
        claim = (
            f"Test '{test.title or test.uri}' was last modified {test_t.date().isoformat()}, "
            f"but the module under test '{target.title or target.uri}' was updated "
            f"{target_t.date().isoformat()} ({delta_days} days newer). The test may no longer "
            "exercise current behavior."
        )
        out.append(DatumInstance(
            datum_qualified_name=datum.qualified_name,
            severity=severity,
            claim=claim,
            evidence={
                "test_source_id": test.source_id,
                "test_modified_at": test_t.isoformat(),
                "code_source_id": target.source_id,
                "code_modified_at": target_t.isoformat(),
                "delta_days": delta_days,
                "threshold_days": threshold_days,
            },
            recommended_action=(
                f"Re-run '{test.title or test.uri}' against '{target.title or target.uri}' "
                "and update the test if the behavior has drifted."
            ),
            cell_refs=list(set(inv.get(test.source_id, []) + inv.get(target.source_id, []))),
            source_refs=[test.source_id, target.source_id],
        ))
    return out


TEST_OLDER_THAN_CODE_UNDER_TEST = Datum(
    name="test_older_than_code_under_test",
    family=DatumFamily.STALENESS,
    tier=DatumTier.PRIMITIVE,
    description="A test cell is older than the code it tests by more than the threshold.",
    inputs={
        "storage_signals": ["file_modified_at", "source_type", "path_pattern"],
        "interaction_signals": [],
        "cube_signals": ["cell_rank", "incident_cells"],
        "text_signals": [],
    },
    semantic_check={
        "claim": "This test predates its module-under-test by more than the threshold.",
        "must_have": ["test_identified", "paired_module_identified", "modified_at_both_sides"],
    },
    syntactic_check={
        "required_fields": ["test_source_id", "code_source_id", "delta_days"],
    },
    output={
        "severity": "medium",
        "claim": "Test {test_source_id} is {delta_days} days older than code {code_source_id}.",
        "evidence": {"test_modified_at": "ISO8601", "code_modified_at": "ISO8601", "delta_days": "int"},
        "recommended_action": "Re-run the test against current code; update if behavior has drifted.",
    },
    examples={
        "positive": {"test": "test_auth.py (2025-01-01)", "code": "auth.py (2026-03-01)", "delta_days": 424},
        "negative": {"test": "test_auth.py (2026-04-15)", "code": "auth.py (2026-04-14)", "delta_days": -1},
    },
    failure_mode=(
        "Overfires on tests that intentionally exercise historical behavior (regression tests pinned to old versions). "
        "Underfires when test naming doesn't follow the `test_<module>.py` convention."
    ),
    composer=_compute_test_older_than_code,
)


# =============================================================================
# PACK REGISTRATION
# =============================================================================

ALL_STALENESS_DATUMS = (
    DOC_OLDER_THAN_CODE,
    SPEC_NEVER_IMPLEMENTED,
    TEST_OLDER_THAN_CODE_UNDER_TEST,
)


def register(registry: DatumRegistry) -> None:
    """Register every datum in the pack. Raises if any fails validation."""
    for d in ALL_STALENESS_DATUMS:
        if d.qualified_name not in registry:
            registry.register(d)
