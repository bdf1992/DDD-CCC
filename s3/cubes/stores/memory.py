"""
InMemoryStore — the first-cut candidate store.

Python-dict backed. Builds a simple inverted index over whitespace-split tokens
for `search_text`. Good for repos with hundreds to low-thousands of candidates;
swap for SQLite / LanceDB when scale demands.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional, Iterable
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRecord
from s3.cubes.stores.base import CandidateStore, SearchHit


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


class InMemoryStore:
    """Dict-backed store with a token inverted index.

    Public state:
        records : dict[source_id -> SourceRecord]
    """
    name = "in-memory"

    def __init__(self) -> None:
        self.records: dict[str, SourceRecord] = {}
        self._index: dict[str, set[str]] = defaultdict(set)  # token -> set[source_id]

    def upsert(self, records: Iterable[SourceRecord]) -> None:
        for rec in records:
            self._remove_from_index(rec.source_id)
            self.records[rec.source_id] = rec
            self._add_to_index(rec)

    def get(self, source_id: str) -> Optional[SourceRecord]:
        return self.records.get(source_id)

    def all(self) -> list[SourceRecord]:
        return list(self.records.values())

    def search_text(self, query: str, limit: int = 10) -> list[SearchHit]:
        q_tokens = {t.lower() for t in _TOKEN_RE.findall(query)}
        if not q_tokens:
            return []
        scored: dict[str, int] = defaultdict(int)
        for token in q_tokens:
            for sid in self._index.get(token, ()):
                scored[sid] += 1
        ranked = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
        hits: list[SearchHit] = []
        for sid, score in ranked[:limit]:
            rec = self.records.get(sid)
            if rec is None:
                continue
            hits.append(SearchHit(
                record=rec,
                score=score / max(1, len(q_tokens)),
                explanation=f"matched {score}/{len(q_tokens)} query tokens",
            ))
        return hits

    def list_changed_since(self, watermark: Optional[str]) -> list[SourceRecord]:
        if watermark is None:
            return self.all()
        return [r for r in self.records.values() if r.observed_at > watermark]

    # --- internals ---

    def _tokenize(self, text: str) -> set[str]:
        return {t.lower() for t in _TOKEN_RE.findall(text or "")}

    def _add_to_index(self, rec: SourceRecord) -> None:
        for t in self._tokenize(rec.body):
            self._index[t].add(rec.source_id)
        if rec.title:
            for t in self._tokenize(rec.title):
                self._index[t].add(rec.source_id)

    def _remove_from_index(self, source_id: str) -> None:
        old = self.records.get(source_id)
        if old is None:
            return
        tokens = self._tokenize(old.body)
        if old.title:
            tokens |= self._tokenize(old.title)
        for t in tokens:
            s = self._index.get(t)
            if s is not None:
                s.discard(source_id)
                if not s:
                    del self._index[t]

    def __len__(self) -> int:
        return len(self.records)
