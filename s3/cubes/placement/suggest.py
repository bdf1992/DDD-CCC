"""
Placement suggester — ranks candidate cells with predictive scores.

Scoring rule (deterministic, no ML):
  score(candidate, cell) =
      classified_type_match_weight * (type_matches_axis_signal ? 1 : 0)
    + vacuum_bonus * (1 if cell is currently empty else 0)
    + rank_prior                        (higher-rank cells slightly preferred
                                         when the candidate has many outbound refs)
    + incidence_bonus * (1 if a currently-placed incident cell shares type with candidate else 0)

The score is a diagnostic, not a decision. The decide step is where commitment
happens; this step just produces ranked candidates for the interview.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


@dataclass
class PlacementCandidate:
    """One proposed cell for a candidate record."""
    cell_label: str
    cell_rank: int
    score: float
    reasons: list[str] = field(default_factory=list)
    predictive: dict = field(default_factory=dict)  # coverage_delta, vacuum_delta, etc.


@dataclass
class PlacementSuggestion:
    """Ranked placements for one candidate."""
    source_id: str
    candidates: list[PlacementCandidate] = field(default_factory=list)

    @property
    def top(self) -> Optional[PlacementCandidate]:
        return self.candidates[0] if self.candidates else None


# Weights — tuned so placements spread across cells rather than all collapsing
# onto the volume. Outbound-refs bonus is sublinear so
# it can't dominate vacuum + type_match; incidence remains strongest once the
# cube starts filling in.
TYPE_MATCH_WEIGHT = 2.0
VACUUM_BONUS = 1.5
RANK_PRIOR_PER_OUTBOUND_REF = 0.05
RANK_PRIOR_OUTBOUND_CAP = 5          # saturate contribution from very linky records
INCIDENCE_BONUS = 1.0
LOAD_PENALTY_PER_OCCUPANT = 0.15     # penalize piling onto already-populated cells


def _candidate_type(record) -> str:
    from s3.cubes.measure import classify_type
    return classify_type(record)


def suggest_placements(record, ir, limit: int = 5) -> PlacementSuggestion:
    """Rank cells in `ir.cube` as placement candidates for `record`.

    Scoring draws on:
      - classified type vs each cell's currently-placed types (type-locality).
      - vacuum status (empty cell is a mild preference — reduces coverage gap).
      - rank prior: higher-rank cells lightly preferred for records with many
        outbound refs (they're more likely to express inter-thing relations).
      - incidence: cells adjacent to currently-placed records of the same type
        get a small bonus (locality of related concepts).

    Returns top-`limit` candidates, sorted by score descending. Ties broken
    alphabetically by cell_label for determinism.
    """
    if ir.cube is None:
        return PlacementSuggestion(source_id=record.source_id)

    cube = ir.cube
    by_id = ir.candidates_by_id()
    rec_type = _candidate_type(record)
    outbound_n = len(record.outbound_refs)

    scored: list[PlacementCandidate] = []
    for cell in cube.all_cells:
        reasons: list[str] = []
        score = 0.0

        placed_here_ids = ir.placements.get(cell.label, [])
        placed_types = {_candidate_type(by_id[i]) for i in placed_here_ids if i in by_id}

        is_vacuum = not placed_here_ids

        # Type-locality: does any placed co-inhabitant share type with candidate?
        if rec_type in placed_types:
            score += TYPE_MATCH_WEIGHT
            reasons.append(f"type_match({rec_type})")

        # Vacuum bonus
        if is_vacuum:
            score += VACUUM_BONUS
            reasons.append("vacuum")

        # Rank prior — sublinear, capped so very linky records don't dominate
        capped_refs = min(outbound_n, RANK_PRIOR_OUTBOUND_CAP)
        score += RANK_PRIOR_PER_OUTBOUND_REF * capped_refs * (cell.rank + 1)
        if outbound_n > 0:
            reasons.append(f"rank_prior(rank={cell.rank}, out_refs={outbound_n})")

        # Load penalty: cells already carrying content cost more to add onto,
        # unless type_match / incidence bonuses already made them attractive.
        if placed_here_ids:
            score -= LOAD_PENALTY_PER_OCCUPANT * len(placed_here_ids)
            reasons.append(f"load_penalty(-{LOAD_PENALTY_PER_OCCUPANT * len(placed_here_ids):.2f})")

        # Incidence bonus: any neighboring cell of the same rank carry matching type?
        incidence_neighbors: set[str] = set()
        for face in cube.faces_of.get(cell, frozenset()):
            incidence_neighbors.add(face.label)
        for coface in cube.cofaces_of.get(cell, frozenset()):
            incidence_neighbors.add(coface.label)
        neighbor_types = set()
        for nb_label in incidence_neighbors:
            for sid in ir.placements.get(nb_label, []):
                if sid in by_id:
                    neighbor_types.add(_candidate_type(by_id[sid]))
        if rec_type in neighbor_types:
            score += INCIDENCE_BONUS
            reasons.append(f"incidence({rec_type})")

        predictive = {
            "current_occupants": len(placed_here_ids),
            "is_vacuum_before": is_vacuum,
            "is_vacuum_after": False,
        }

        scored.append(PlacementCandidate(
            cell_label=cell.label,
            cell_rank=cell.rank,
            score=round(score, 6),
            reasons=reasons,
            predictive=predictive,
        ))

    # Sort by score desc, cell label asc (deterministic tiebreak)
    scored.sort(key=lambda c: (-c.score, c.cell_label))
    return PlacementSuggestion(source_id=record.source_id, candidates=scored[:limit])
