"""
s3.cubes.profile — Profile Card assembly + axis proposal from adapter output.

The derive -> present -> refine protocol applied to axis choice.
Reads adapter output + existing project artifacts; proposes a Profile Card
and V=3 axis convention with per-axis evidence citations. Enforces universal
cube invariants (V=3 distinct axes, cross-rank coverage, non-empty support).

Exploit, don't invent: Profile Card is assembled from existing SourceRecord
fields, not new extraction. Axis proposer reads distributions over already-
extracted signals. Universal invariants are cube-structural.
"""

from s3.cubes.profile.card import (
    ProfileCard,
    assemble_profile_card,
)
from s3.cubes.profile.invariants import (
    InvariantError,
    validate_axis_proposal,
    UNIVERSAL_INVARIANTS,
)
from s3.cubes.profile.axis_proposer import (
    AxisProposal,
    propose_axes,
)
from s3.cubes.profile.axis_convention import (
    AxisConvention,
    commit_convention,
)

__all__ = [
    "ProfileCard", "assemble_profile_card",
    "InvariantError", "validate_axis_proposal", "UNIVERSAL_INVARIANTS",
    "AxisProposal", "propose_axes",
    "AxisConvention", "commit_convention",
]
