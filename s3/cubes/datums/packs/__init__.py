"""
s3.cubes.datums.packs — bundled reference datum packs.

A pack is a set of related datums shipped together. Each pack exposes:
    register(registry: DatumRegistry) -> None   # registers every datum in the pack

Current packs:
    staleness   — StalenessDatumPack: first reference pack.

Planned packs:
    composition — prose_to_code_ratio, test_to_code_ratio, ...
    vocabulary  — unmapped_term, orphan_vocabulary, term_drift
    structural  — vacuum_cell, frustrated_edge, isolated_vertex
    meta        — unreviewed_placement, disagreement_heavy_region

Users may author their own packs via the `datum-design` skill.
"""
from s3.cubes.datums.packs.staleness import (
    DOC_OLDER_THAN_CODE,
    SPEC_NEVER_IMPLEMENTED,
    TEST_OLDER_THAN_CODE_UNDER_TEST,
    register as register_staleness_pack,
)


def register_all(registry) -> None:
    """Register every shipped pack's datums into the given registry."""
    register_staleness_pack(registry)


__all__ = [
    "DOC_OLDER_THAN_CODE",
    "SPEC_NEVER_IMPLEMENTED",
    "TEST_OLDER_THAN_CODE_UNDER_TEST",
    "register_staleness_pack",
    "register_all",
]
