"""
CandidateStore Protocol — the boundary between adapters and the rest of the
cube pipeline.

Stores hold normalized SourceRecords (from adapters) plus any derived
measurement attachments, and provide three kinds of lookup:
    - by id:       get(source_id) -> SourceRecord
    - by text:     search_text(query, limit) -> list[SearchHit]
    - by vector:   search_vector(vector, limit) -> list[SearchHit]

A fourth — contextual RAG — is a higher-level search that combines content
similarity with cell locality. It's defined here as an optional method that
stores may skip.

Invariant: stores never write to the cube. They index what adapters
produce so the placement engine can query efficiently.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Optional, Iterable
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRecord


@dataclass
class SearchHit:
    """A retrieval result: the candidate record + a score + optional explanation."""
    record: SourceRecord
    score: float
    explanation: Optional[str] = None


class CandidateStore(Protocol):
    """Minimum store surface. Additional methods (vector / contextual) are
    optional and may return `NotImplementedError` on stores that don't support
    them — callers check via `hasattr`."""

    def upsert(self, records: Iterable[SourceRecord]) -> None:
        """Insert or update canonical records by source_id. Atomic per record."""
        ...

    def get(self, source_id: str) -> Optional[SourceRecord]:
        """Return the record with this id, or None if absent."""
        ...

    def all(self) -> list[SourceRecord]:
        """Full dump. Safe on small stores; reconsider at scale."""
        ...

    def search_text(self, query: str, limit: int = 10) -> list[SearchHit]:
        """Literal / keyword-ish text match. Stores with richer text indexes
        (BM25, full-text) extend; minimal stores do substring matching."""
        ...

    def list_changed_since(self, watermark: Optional[str]) -> list[SourceRecord]:
        """Records whose `observed_at` is > watermark. Returns all if None."""
        ...
