"""
s3.cubes.placement — Placement engine.

Three-step pipeline: suggest -> decide -> emit.

    suggest(candidate, ir)     -> PlacementSuggestion (ranked cells + predictive scores)
    decide(ir, decision)       -> (updated ir, signed datapoint)
    emit(datapoint, stream)    -> write Greenfield-shape hash-chained JSONL

The decide step is the only path that mutates cube state. Every mutation
emits a signed datapoint appended to the provenance chain.
"""

from s3.cubes.placement.suggest import (
    PlacementCandidate,
    PlacementSuggestion,
    suggest_placements,
)
from s3.cubes.placement.decide import (
    PlacementDecision,
    DecisionKind,
    apply_decision,
)
from s3.cubes.placement.emit import (
    emit_datapoint,
    write_jsonl_stream,
    SignedDatapoint,
)

__all__ = [
    "PlacementCandidate", "PlacementSuggestion", "suggest_placements",
    "PlacementDecision", "DecisionKind", "apply_decision",
    "SignedDatapoint", "emit_datapoint", "write_jsonl_stream",
]
