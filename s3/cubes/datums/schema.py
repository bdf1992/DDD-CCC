"""
Datum schema — serialize / deserialize Datum specs as YAML (or JSON).

The canonical datum YAML contract:

    name: doc_older_than_code
    family: staleness
    tier: primitive
    description: A doc cell is older than the code it references.
    inputs:
      storage_signals: [file_modified_at, source_type]
      interaction_signals: []
      cube_signals: [cell_rank, incident_cells]
      text_signals: [outbound_refs]
    semantic_check:
      claim: "This documentation predates the code it links to by more than the threshold."
      must_have: [cited_code_target, modified_at_both_sides, age_threshold]
    syntactic_check:
      required_fields: [doc_source_id, code_source_id, delta_days]
    output:
      severity: medium
      claim: "Doc {doc_source_id} is {delta_days} days older than code {code_source_id}."
      evidence: {doc_modified: "...", code_modified: "..."}
      recommended_action: "Review and update the documentation."
    examples:
      positive:
        doc: docs/guide.md (2024-01-01)
        code: src/main.py (2026-04-01)
        delta_days: 821
      negative:
        doc: docs/guide.md (2026-04-15)
        code: src/main.py (2026-04-01)
        delta_days: -14
    failure_mode: "Overfires on intentionally-historical docs; underfires when doc has no link."
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.datums.base import (
    Datum, DatumFamily, DatumTier,
    validate_datum, ValidationError,
)


def load_datum_from_dict(d: dict, composer: Optional[callable] = None) -> Datum:
    """Build a Datum from a dict (parsed YAML / JSON). Validates before return.

    Raises ValidationError if the resulting datum fails the refusal rule.
    """
    missing = [k for k in ("name", "family", "tier", "description") if k not in d]
    if missing:
        raise ValidationError([f"missing top-level key: {k}" for k in missing])

    try:
        family = DatumFamily(d["family"])
    except ValueError:
        raise ValidationError([
            f"family: '{d['family']}' is not a valid family "
            f"(expected one of {[f.value for f in DatumFamily]})"
        ])
    try:
        tier = DatumTier(d["tier"])
    except ValueError:
        raise ValidationError([
            f"tier: '{d['tier']}' is not a valid tier "
            f"(expected one of {[t.value for t in DatumTier]})"
        ])

    datum = Datum(
        name=d["name"],
        family=family,
        tier=tier,
        description=d["description"],
        inputs=d.get("inputs", {}) or {},
        semantic_check=d.get("semantic_check", {}) or {},
        syntactic_check=d.get("syntactic_check", {}) or {},
        output=d.get("output", {}) or {},
        examples=d.get("examples", {}) or {},
        failure_mode=d.get("failure_mode", "") or "",
        composer=composer,
    )

    errs = validate_datum(datum)
    if errs:
        raise ValidationError(errs)
    return datum


def load_datum_from_file(path: Path | str, composer: Optional[callable] = None) -> Datum:
    """Load a Datum from a .yaml / .yml / .json file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        d = yaml.safe_load(text)
    elif p.suffix.lower() == ".json":
        d = json.loads(text)
    else:
        # Try YAML first (superset of JSON for most cases), fall back to JSON.
        try:
            d = yaml.safe_load(text)
        except yaml.YAMLError:
            d = json.loads(text)
    if not isinstance(d, dict):
        raise ValidationError([f"{path}: top-level must be a mapping, got {type(d).__name__}"])
    return load_datum_from_dict(d, composer=composer)


def datum_to_dict(datum: Datum) -> dict:
    """Serialize a Datum spec to a dict (round-trips through load_datum_from_dict)."""
    return {
        "name": datum.name,
        "family": datum.family.value,
        "tier": datum.tier.value,
        "description": datum.description,
        "inputs": datum.inputs,
        "semantic_check": datum.semantic_check,
        "syntactic_check": datum.syntactic_check,
        "output": datum.output,
        "examples": datum.examples,
        "failure_mode": datum.failure_mode,
    }


def datum_to_yaml(datum: Datum) -> str:
    """Emit a Datum as a YAML document string."""
    return yaml.safe_dump(datum_to_dict(datum), sort_keys=False, default_flow_style=False)
