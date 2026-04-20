"""
s3.cubes.ir — Knowledge IR (intermediate representation).

The canonical in-memory reduction of the signed datapoint stream. Bundles
candidates, placements, datum instances, metric outputs, cube structural
context, axis convention, and provenance.

Consumed by the datum-first dashboard and (later) the Knowledge Shape Engine.

Rule (from the Datum-Preserving Knowledge Loop doctrine): cube state is a
deterministic reduction of the signed datapoint stream. KnowledgeIR is that
reduction as an in-memory object.
"""

from s3.cubes.ir.graph import (
    KnowledgeIR,
    KnowledgeIRSnapshot,
    empty_ir,
)

__all__ = [
    "KnowledgeIR",
    "KnowledgeIRSnapshot",
    "empty_ir",
]
