"""
s3.cubes.datums — Datum dataclass, registry, schema validator.

The product layer above metrics. Metrics read cube state. Datums compose
metrics + adapter content to surface meaning (staleness, composition,
vocabulary gaps, structural frustrations).

This module ships the plumbing:
    Datum            — canonical dataclass matching the YAML contract
    DatumRegistry    — registration / lookup / listing
    validate_datum   — enforces the refusal rule (no datum without evidence +
                       examples + failure mode)

Datum packs (StalenessDatumPack and friends) register via the
datum-design skill.
"""

from s3.cubes.datums.base import (
    Datum,
    DatumTier,
    DatumFamily,
    DatumRegistry,
    DatumContext,
    DatumInstance,
    ValidationError,
    validate_datum,
)
from s3.cubes.datums.schema import (
    load_datum_from_dict,
    load_datum_from_file,
    datum_to_dict,
    datum_to_yaml,
)
from s3.cubes.datums.composer import standard_declarative_composer

__all__ = [
    "Datum", "DatumTier", "DatumFamily",
    "DatumContext", "DatumInstance",
    "DatumRegistry",
    "ValidationError",
    "validate_datum",
    "load_datum_from_dict", "load_datum_from_file",
    "datum_to_dict", "datum_to_yaml",
    "standard_declarative_composer",
]
