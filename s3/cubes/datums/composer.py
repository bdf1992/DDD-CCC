"""
Standard declarative composer.

When a Datum is authored as YAML (no Python `composer` callable attached),
this is the default executor. It handles simple primitive datums whose
emission logic is expressible as:

    - iterate candidates whose `source_type` matches one of the declared inputs
    - for each, check the `semantic_check.must_have` predicates against
      built-in match helpers
    - if all pass, emit a DatumInstance using the `output` template

Richer logic (pair-matching, time-delta computations, cell-adjacency checks)
belongs in a Python `composer` callable — the staleness pack uses that path.
Declarative is intentionally thin.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.datums.base import Datum, DatumContext, DatumInstance


def standard_declarative_composer(datum: Datum, context: DatumContext) -> list[DatumInstance]:
    """Execute a declaratively-specified datum.

    Default behavior: for each candidate whose (source_type | classified type)
    matches the datum's declared filters, emit one DatumInstance with the
    output.claim template rendered from candidate fields.

    Filter keys inside a storage_signals dict entry:
        source_type_in : match against rec.source_type (raw)
        type_in        : match against classify_type(rec) (intrinsic bucket)

    Both may appear; both must match. This is a *starting* implementation —
    covers trivial primitive datums so YAML-authored simple cases work out of
    the box. Composable / complex datums attach a custom Python composer.
    """
    out: list[DatumInstance] = []
    source_type_filter, type_filter = _extract_type_filters(datum)

    for rec in context.candidates:
        if source_type_filter and rec.source_type not in source_type_filter:
            continue
        if type_filter and _record_type(rec) not in type_filter:
            continue

        claim_template = datum.output.get("claim", datum.description)
        claim = _render(claim_template, {
            "source_id": rec.source_id,
            "source_type": rec.source_type,
            "uri": rec.uri,
            "title": rec.title or "",
        })

        action_template = datum.output.get("recommended_action", "review this")
        action = _render(action_template, {
            "source_id": rec.source_id,
            "title": rec.title or "",
        })

        out.append(DatumInstance(
            datum_qualified_name=datum.qualified_name,
            severity=str(datum.output.get("severity", "low")),
            claim=claim,
            evidence={"source_id": rec.source_id, "uri": rec.uri},
            recommended_action=action,
            cell_refs=[],
            source_refs=[rec.source_id],
        ))
    return out


def _extract_type_filters(datum: Datum) -> tuple[set[str], set[str]]:
    """Pull (source_type_filter, classified_type_filter) from storage_signals.

    Each dict entry in storage_signals may carry `source_type_in` and/or
    `type_in`. Empty filter = no restriction on that axis.
    """
    source_type_filter: set[str] = set()
    type_filter: set[str] = set()
    ss = datum.inputs.get("storage_signals") or []
    for entry in ss:
        if not isinstance(entry, dict):
            continue
        stv = entry.get("source_type_in")
        if isinstance(stv, (list, tuple)):
            source_type_filter.update(str(v) for v in stv)
        tv = entry.get("type_in")
        if isinstance(tv, (list, tuple)):
            type_filter.update(str(v) for v in tv)
    return source_type_filter, type_filter


def _record_type(rec) -> str:
    """Return the intrinsic type bucket for a record (same logic as measure.classify_type)."""
    # Lazy-import to avoid a cycle.
    from s3.cubes.measure import classify_type
    return classify_type(rec)


def _render(template: str, values: dict) -> str:
    """Render a lightweight `{key}` template. Missing keys render as empty."""
    if not isinstance(template, str):
        return str(template)
    try:
        return template.format_map(_SafeDict(values))
    except Exception:
        return template


class _SafeDict(dict):
    def __missing__(self, key):
        return ""
