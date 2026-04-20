"""
GreenfieldJsonlAdapter — reads a Greenfield export directory.

Greenfield stores its protocol primitives as append-only JSONL journals:
    source.jsonl, datapoint.jsonl, mapping.jsonl, insight.jsonl, gap.jsonl,
    build.jsonl, cycle.jsonl, profile.jsonl, mulch.jsonl, term.jsonl, idea.jsonl.

Each row in any of these files becomes a SourceRecord. The `source_type` field
preserves the Greenfield primitive kind (source / datapoint / mapping / etc.),
so downstream placement + measurement can reason about primitive identity.

Invariant: no lifting or interpretation happens at the adapter layer. Semantic
lifts (e.g. "this datapoint cites this source") are the placement engine's job.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRef, SourceRecord, SourceAdapter


_JSONL_FILES = (
    "source", "datapoint", "mapping", "insight", "gap",
    "build", "cycle", "profile", "mulch", "term", "idea",
)


class GreenfieldJsonlAdapter:
    """Reads a Greenfield export directory of append-only JSONL journals.

    Config:
        export_root : directory containing `<primitive>.jsonl` files.
        primitives  : tuple of primitive kinds to read. Defaults to all known.

    Emits source_type = f"greenfield_{primitive}" for each row (e.g.
    "greenfield_source", "greenfield_datapoint", "greenfield_cycle").
    """
    name = "greenfield-jsonl"

    def __init__(
        self,
        export_root: Path | str,
        primitives: tuple[str, ...] = _JSONL_FILES,
    ):
        self.export_root = Path(export_root).resolve()
        self.primitives = primitives

    def _iter_jsonl(self):
        for kind in self.primitives:
            path = self.export_root / f"{kind}.jsonl"
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, start=1):
                    s = line.strip()
                    if not s:
                        continue
                    yield kind, path, line_no, s

    def discover(self) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for kind, path, line_no, raw in self._iter_jsonl():
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rid = obj.get("id") or obj.get("source_id") or obj.get(f"{kind}_id") or f"{kind}-{line_no}"
            uri = f"greenfield://{self.export_root.name}/{kind}/{rid}"
            refs.append(SourceRef(
                adapter=self.name,
                uri=uri,
                opaque=(str(path), line_no),
            ))
        return refs

    def read(self, ref: SourceRef) -> SourceRecord:
        path_str, line_no = ref.opaque
        path = Path(path_str)
        obj = None
        with path.open("r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, start=1):
                if i == line_no:
                    s = line.strip()
                    if s:
                        obj = json.loads(s)
                    break
        if obj is None:
            raise ValueError(f"no row at {path}:{line_no}")

        kind = path.stem
        rid = obj.get("id") or obj.get("source_id") or obj.get(f"{kind}_id") or f"{kind}-{line_no}"
        title = obj.get("title") or obj.get("name") or obj.get("claim") or str(rid)
        body = _synthesize_body(kind, obj)
        observed = datetime.now(tz=timezone.utc).isoformat()
        outbound = _extract_outbound_refs(obj)

        return SourceRecord(
            source_id=ref.stable_id(),
            source_type=f"greenfield_{kind}",
            uri=ref.uri,
            title=title,
            body=body,
            metadata={
                "primitive": kind,
                "row_id": rid,
                "jsonl_path": str(path),
                "line_no": line_no,
                "raw": obj,
            },
            version_hash=SourceRecord.fingerprint(body),
            observed_at=observed,
            parent_refs=[f"greenfield://{self.export_root.name}/{kind}"],
            outbound_refs=outbound,
        )

    def changed_since(self, watermark: Optional[str]) -> list[SourceRef]:
        # JSONL is append-only; without an embedded timestamp convention we
        # return discover() unconditionally. Adapters with native timestamps
        # (via obj["observed_at"] or similar) can tighten later.
        return self.discover()


def _synthesize_body(kind: str, obj: dict) -> str:
    """Produce a canonical text body from a structured row.

    The body is what placement + base measurements read. For Greenfield rows,
    we concatenate human-readable fields in a stable order: title, claim,
    description, body, notes — skipping missing fields.
    """
    parts: list[str] = []
    for field in ("title", "name", "claim", "description", "body", "text", "notes", "summary"):
        val = obj.get(field)
        if isinstance(val, str) and val.strip():
            parts.append(f"{field.upper()}: {val.strip()}")
    if not parts:
        # Fall back to a JSON dump so body is non-empty and fingerprintable.
        parts.append(json.dumps(obj, sort_keys=True))
    return "\n\n".join(parts)


def _extract_outbound_refs(obj: dict) -> list[str]:
    """Pull reference-shaped fields out of a row.

    Recognizes common Greenfield conventions: `prior_hash`, `source_ids`,
    `cited_sources`, `mapped_to`, `from`, `to`, `refs`. Not exhaustive;
    extended as we see more Greenfield row shapes.
    """
    out: list[str] = []
    for field in ("prior_hash", "source_id", "mapped_to", "from", "to",
                  "cites", "refs", "evidence_refs"):
        val = obj.get(field)
        if isinstance(val, str) and val.strip():
            out.append(val.strip())
        elif isinstance(val, list):
            out.extend(str(x).strip() for x in val if x)
    for field in ("source_ids", "cited_sources"):
        val = obj.get(field)
        if isinstance(val, list):
            out.extend(str(x).strip() for x in val if x)
    return out
