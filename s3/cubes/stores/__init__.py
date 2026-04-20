"""
s3.cubes.stores — Candidate store adapters.

A store answers: "Where do candidates and lookup indexes live?"

The store is NOT the truth model. It is a retrieval / cache / index layer.
The truth model is the signed datapoint stream + the cube placement history.

First store: InMemoryStore. SQLite / LanceDB / Chroma deferred until scale
demands them.
"""

from s3.cubes.stores.base import CandidateStore, SearchHit
from s3.cubes.stores.memory import InMemoryStore

__all__ = [
    "CandidateStore", "SearchHit",
    "InMemoryStore",
]
