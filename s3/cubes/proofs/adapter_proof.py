"""
adapter_proof — four-proof runner for SourceAdapter modules.

Adapter-specific requirements on top of the base four proofs:
  - pressure event must carry `{adapter_name, cell_candidates, witness}` at minimum
  - datum instances must carry `evidence` citing at least one SourceRecord.source_id
  - corrective event applies an adapter-specific whitelist/override, then
    re-runs the datum pipeline; pre/post datum counts must differ
  - dual-test: a tests module exposing run() that exercises discover/read on
    a fixture directory + run_skill_test(fixture) that follows adapter-design

The harness does not instantiate the adapter. The caller passes the already-
instantiated adapter into the fixture (typically a dataclass holding
(adapter, fixture_path, ...)) — per-adapter fixture shape is in the adapter's
test module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.proofs.harness import (
    ProofDeclaration,
    ProofReport,
    green_report,
    check_pressure,
    check_datum,
    check_corrective,
    check_dual_test,
)


ADAPTER_PRESSURE_FIELDS = ("adapter_name", "cell_candidates", "witness")


def verify_adapter(adapter: Any, fixture: Any,
                   correction_event: dict) -> ProofReport:
    """Run the four proofs against an adapter module.

    The adapter must expose a `PROOF` classvar (or module-level `PROOF`) of
    type ProofDeclaration. `fixture` is opaque to this runner and passed
    through to the declared callables — the adapter's test module defines
    the expected fixture shape.
    """
    name = getattr(adapter, "name", adapter.__class__.__name__)
    decl = _get_decl(adapter)
    if decl is None:
        from s3.cubes.proofs.harness import _fail
        return ProofReport(
            module_kind="adapter",
            module_name=name,
            results=[
                _fail("adapter", name, "pressure",
                      "adapter has no PROOF attribute; not provable"),
                _fail("adapter", name, "datum",
                      "adapter has no PROOF attribute; not provable"),
                _fail("adapter", name, "corrective",
                      "adapter has no PROOF attribute; not provable"),
                _fail("adapter", name, "dual_test",
                      "adapter has no PROOF attribute; not provable"),
            ],
        )

    results = [
        check_pressure(decl, fixture, ADAPTER_PRESSURE_FIELDS, "adapter", name),
        check_datum(decl, fixture, "adapter", name),
        check_corrective(decl, fixture, correction_event, "adapter", name),
        check_dual_test(decl, "adapter", name),
    ]
    return green_report("adapter", name, results)


def _get_decl(adapter: Any):
    """Look up PROOF on instance, class, or module (in that order)."""
    d = getattr(adapter, "PROOF", None)
    if d is not None:
        return d
    # Class-level
    d = getattr(type(adapter), "PROOF", None)
    if d is not None:
        return d
    # Module-level
    mod_name = type(adapter).__module__
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        return getattr(mod, "PROOF", None)
    except Exception:
        return None
