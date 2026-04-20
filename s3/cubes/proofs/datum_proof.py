"""
datum_proof — four-proof runner for datum pack modules.

Datum-pack-specific requirements on top of the base four proofs:
  - pressure event must carry {pack_name, datums, fires_at}
  - datum instances cite source records + cells + measurement provenance
  - corrective event: user rejects a datum instance with a reason; pack
    re-runs and the rejected instance must be absent (or flagged resolved)
  - dual-test: test module exercises the pack against a fixture cube + sources

The datum YAML + registry discipline is orthogonal — it handles the
*declarative* shape of datums (refusal rule). The proof harness verifies
the *executable* shape against real data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.proofs.harness import (
    ProofReport,
    green_report,
    check_pressure,
    check_datum,
    check_corrective,
    check_dual_test,
    _fail,
)


DATUM_PACK_PRESSURE_FIELDS = ("pack_name", "datums", "fires_at")


def verify_datum_pack(pack_module: Any, fixture: Any,
                      correction_event: dict) -> ProofReport:
    """Run the four proofs against a datum pack module."""
    name = getattr(pack_module, "__name__", "unknown").rsplit(".", 1)[-1]
    decl = getattr(pack_module, "PROOF", None)
    if decl is None:
        return ProofReport(
            module_kind="datum_pack",
            module_name=name,
            results=[
                _fail("datum_pack", name, "pressure", "module has no PROOF attribute"),
                _fail("datum_pack", name, "datum", "module has no PROOF attribute"),
                _fail("datum_pack", name, "corrective", "module has no PROOF attribute"),
                _fail("datum_pack", name, "dual_test", "module has no PROOF attribute"),
            ],
        )
    results = [
        check_pressure(decl, fixture, DATUM_PACK_PRESSURE_FIELDS, "datum_pack", name),
        check_datum(decl, fixture, "datum_pack", name),
        check_corrective(decl, fixture, correction_event, "datum_pack", name),
        check_dual_test(decl, "datum_pack", name),
    ]
    return green_report("datum_pack", name, results)
