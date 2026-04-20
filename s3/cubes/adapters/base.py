"""
Canonical types at the adapter boundary: SourceRef, SourceRecord, SourceAdapter.

Every external knowledge system — Markdown files, Obsidian vaults, Greenfield
JSONL journals, later JIRA / Postgres / vector docs — normalizes through these
types. After normalization, candidates from disparate origins become comparable.

Contract:
    discover()      -> list of SourceRef  (lightweight references)
    read(ref)       -> SourceRecord       (full canonical record)
    changed_since() -> list of SourceRef  (incremental ingest)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


@dataclass(frozen=True)
class SourceRef:
    """Lightweight reference to a source object. Cheap to enumerate; does not
    carry the body. `opaque` is adapter-internal metadata for faster re-read."""
    adapter: str
    uri: str
    opaque: tuple = field(default_factory=tuple)

    def stable_id(self) -> str:
        """Canonical id: <adapter>::<sha256-8 of uri>. Deterministic."""
        h = hashlib.sha256(self.uri.encode("utf-8")).hexdigest()[:16]
        return f"{self.adapter}::{h}"


@dataclass
class SourceRecord:
    """Canonical, adapter-agnostic candidate. Every adapter emits this shape.

    source_id     : stable id (derivable from SourceRef.stable_id)
    source_type   : "markdown" / "obsidian_note" / "greenfield_source" / etc.
    uri           : original path / URL / API id / db key
    title         : inferred or declared; may be None
    body          : canonical textual content
    metadata      : source-type-specific fields preserved verbatim
    version_hash  : sha256 of body — content fingerprint
    observed_at   : ISO 8601 timestamp of adapter read
    parent_refs   : containing refs (parent dir / parent doc / parent record)
    outbound_refs : outgoing refs (wikilinks / imports / citations / foreign keys)
    """
    source_id: str
    source_type: str
    uri: str
    title: Optional[str]
    body: str
    metadata: dict
    version_hash: str
    observed_at: str
    parent_refs: list[str] = field(default_factory=list)
    outbound_refs: list[str] = field(default_factory=list)

    @staticmethod
    def fingerprint(body: str) -> str:
        """Canonical content hash. Stable across adapter versions."""
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


class SourceAdapter(Protocol):
    """Protocol every source adapter must satisfy.

    `name` is a stable adapter identifier, used in SourceRef.adapter and in
    stable_id() prefixes. Keep it short and lowercase: "markdown", "obsidian",
    "greenfield-jsonl", "jira", "postgres", "vector-store".
    """
    name: str

    def discover(self) -> list[SourceRef]:
        """Enumerate all sources this adapter can read. Cheap; no body fetch."""
        ...

    def read(self, ref: SourceRef) -> SourceRecord:
        """Hydrate a ref into a full SourceRecord."""
        ...

    def changed_since(self, watermark: Optional[str]) -> list[SourceRef]:
        """Incremental: return refs modified since watermark (ISO 8601 or None).

        Adapters without native modification tracking may return discover() output
        unconditionally (correctness over efficiency for first cut).
        """
        ...
