"""
Datum dataclass + DatumRegistry + schema validator.

Canonical datum contract:

    name: <snake_case_id>
    family: staleness | composition | vocabulary | structural | meta
    tier: primitive | composable | complex
    description: <one-line claim>
    inputs: dict with storage_signals, interaction_signals, cube_signals, text_signals
    semantic_check: {claim, must_have[]}
    syntactic_check: {required_fields[]}
    output: {severity, claim, evidence, recommended_action}
    examples: {positive, negative}
    failure_mode: <what goes wrong if it overfires or underfires>

The refusal rule (load-bearing): a datum cannot register unless ALL of
semantic_check, syntactic_check, examples.positive, examples.negative, and
failure_mode are present and non-empty. This prevents natural-language-only
datums from polluting the registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if TYPE_CHECKING:
    from s3.cubes.adapters.base import SourceRecord
    from s3.cubes.combinatorial_complex import CubeComplex


class DatumTier(str, Enum):
    PRIMITIVE = "primitive"
    COMPOSABLE = "composable"
    COMPLEX = "complex"


class DatumFamily(str, Enum):
    STALENESS = "staleness"
    COMPOSITION = "composition"
    VOCABULARY = "vocabulary"
    STRUCTURAL = "structural"
    META = "meta"


class ValidationError(Exception):
    """Raised by validate_datum when the refusal rule fires."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass
class Datum:
    """Canonical datum spec. Matches the YAML contract 1:1."""
    name: str
    family: DatumFamily
    tier: DatumTier
    description: str
    inputs: dict                       # {storage_signals, interaction_signals, cube_signals, text_signals}
    semantic_check: dict               # {claim, must_have}
    syntactic_check: dict              # {required_fields}
    output: dict                       # {severity, claim, evidence, recommended_action}
    examples: dict                     # {positive, negative}
    failure_mode: str
    composer: Optional[Callable] = None  # None = use standard declarative composer

    @property
    def qualified_name(self) -> str:
        return f"{self.family.value}.{self.name}"

    def execute(self, context: "DatumContext") -> list["DatumInstance"]:
        """Run this datum against a context, returning emitted instances.

        If `composer` is set, delegates to it. Otherwise uses the standard
        declarative composer (which handles simple primitive datums).
        """
        if self.composer is not None:
            return self.composer(self, context)
        from s3.cubes.datums.composer import standard_declarative_composer
        return standard_declarative_composer(self, context)


@dataclass
class DatumContext:
    """Everything a datum needs to compute its instances.

    candidates : all SourceRecords the cube has seen
    placements : cell_label -> list[source_id]. May be empty pre-Phase-4.
    cube       : the CubeComplex (rank 0/1/2/3 structure). Optional.
    now        : ISO 8601 reference time for age computations. Defaults to utcnow.
    """
    candidates: list
    placements: dict
    cube: Optional[object] = None
    now: Optional[str] = None

    def __post_init__(self):
        if self.now is None:
            self.now = datetime.now(tz=timezone.utc).isoformat()

    def candidates_by_id(self) -> dict[str, object]:
        return {c.source_id: c for c in self.candidates}

    def candidates_at_cell(self, cell_label: str) -> list:
        ids = set(self.placements.get(cell_label, ()))
        return [c for c in self.candidates if c.source_id in ids]


@dataclass
class DatumInstance:
    """One emitted claim from a datum's execution against a context.

    datum_qualified_name : family.name of the producing datum.
    severity             : low / medium / high.
    claim                : filled-in claim template (human-readable).
    evidence             : dict matching the Datum.output.evidence schema.
    recommended_action   : what a human or LLM should do about this.
    cell_refs            : cell labels this instance grounds in.
    source_refs          : source_ids contributing evidence.
    observed_at          : ISO 8601 timestamp.
    """
    datum_qualified_name: str
    severity: str
    claim: str
    evidence: dict
    recommended_action: str
    cell_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    observed_at: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(tz=timezone.utc).isoformat()


# =============================================================================
# VALIDATION — the refusal rule
# =============================================================================

_REQUIRED_INPUT_SECTIONS = ("storage_signals", "interaction_signals",
                            "cube_signals", "text_signals")


def validate_datum(datum: Datum) -> list[str]:
    """Check a datum against the refusal rule. Returns list of error strings;
    empty list means the datum is registerable."""
    errs: list[str] = []

    if not datum.name or not datum.name.strip():
        errs.append("name: must be non-empty snake_case identifier")
    elif not datum.name.replace("_", "").replace("-", "").isalnum():
        errs.append(f"name: '{datum.name}' must be snake_case (letters/digits/underscore)")

    if not isinstance(datum.family, DatumFamily):
        errs.append(f"family: must be a DatumFamily enum member, got {type(datum.family).__name__}")

    if not isinstance(datum.tier, DatumTier):
        errs.append(f"tier: must be a DatumTier enum member, got {type(datum.tier).__name__}")

    if not datum.description or not datum.description.strip():
        errs.append("description: must be a non-empty one-line claim")

    # inputs — at least one input section must be non-empty.
    if not isinstance(datum.inputs, dict):
        errs.append("inputs: must be a dict")
    else:
        if not any(datum.inputs.get(s) for s in _REQUIRED_INPUT_SECTIONS):
            errs.append(
                "inputs: at least one of "
                f"{list(_REQUIRED_INPUT_SECTIONS)} must be non-empty"
            )

    # semantic_check
    sc = datum.semantic_check or {}
    if not sc.get("claim") or not str(sc["claim"]).strip():
        errs.append("semantic_check.claim: must be a non-empty human-readable claim")
    if not sc.get("must_have") or not isinstance(sc["must_have"], list) or not sc["must_have"]:
        errs.append("semantic_check.must_have: must be a non-empty list of required evidence kinds")

    # syntactic_check
    syc = datum.syntactic_check or {}
    if not syc.get("required_fields") or not isinstance(syc["required_fields"], list) or not syc["required_fields"]:
        errs.append("syntactic_check.required_fields: must be a non-empty list of required field names")

    # output
    outp = datum.output or {}
    for f in ("severity", "claim", "recommended_action"):
        if not outp.get(f):
            errs.append(f"output.{f}: must be set")

    # examples
    ex = datum.examples or {}
    if not ex.get("positive"):
        errs.append("examples.positive: must provide one concrete matching case")
    if not ex.get("negative"):
        errs.append("examples.negative: must provide one near-miss that should NOT match")

    # failure_mode
    if not datum.failure_mode or not datum.failure_mode.strip():
        errs.append("failure_mode: must describe what goes wrong if the datum overfires or underfires")

    return errs


# =============================================================================
# REGISTRY
# =============================================================================

class DatumRegistry:
    """In-process datum registry.

    Enforces the refusal rule on register(); raises ValidationError on failure.
    Lookup by qualified name `<family>.<name>`. List by tier / family filters.
    """

    def __init__(self) -> None:
        self._datums: dict[str, Datum] = {}

    def register(self, datum: Datum) -> None:
        errs = validate_datum(datum)
        if errs:
            raise ValidationError(errs)
        qn = datum.qualified_name
        if qn in self._datums:
            raise ValueError(f"datum already registered: {qn}")
        self._datums[qn] = datum

    def get(self, qualified_name: str) -> Optional[Datum]:
        return self._datums.get(qualified_name)

    def list(
        self,
        family: Optional[DatumFamily] = None,
        tier: Optional[DatumTier] = None,
    ) -> list[Datum]:
        out = list(self._datums.values())
        if family is not None:
            out = [d for d in out if d.family == family]
        if tier is not None:
            out = [d for d in out if d.tier == tier]
        return sorted(out, key=lambda d: d.qualified_name)

    def __len__(self) -> int:
        return len(self._datums)

    def __contains__(self, qualified_name: str) -> bool:
        return qualified_name in self._datums
