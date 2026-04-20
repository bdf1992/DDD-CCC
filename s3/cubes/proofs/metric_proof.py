"""
metric_proof — four-proof runner for MetricPlugin modules.

Metric-specific requirements on top of the base four proofs:
  - pressure event must carry {metric_name, cells, threshold, fires_at}
  - datum instances cite measurement outputs + cell ids
  - corrective event applies a user override (e.g., "this vacuum is intentional")
    and the metric's subsequent output must down-weight / exclude that cell
  - dual-test: test module exercises the metric against a fixture IR

Metrics are simpler than adapters — their PROOF may live at module level.
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


METRIC_PRESSURE_FIELDS = ("metric_name", "cells", "threshold", "fires_at")


def verify_metric(metric_module: Any, fixture: Any,
                  correction_event: dict) -> ProofReport:
    """Run the four proofs against a metric module (imported module object)."""
    name = getattr(metric_module, "__name__", "unknown").rsplit(".", 1)[-1]
    decl = getattr(metric_module, "PROOF", None)
    if decl is None:
        return ProofReport(
            module_kind="metric",
            module_name=name,
            results=[
                _fail("metric", name, "pressure", "module has no PROOF attribute"),
                _fail("metric", name, "datum", "module has no PROOF attribute"),
                _fail("metric", name, "corrective", "module has no PROOF attribute"),
                _fail("metric", name, "dual_test", "module has no PROOF attribute"),
            ],
        )
    results = [
        check_pressure(decl, fixture, METRIC_PRESSURE_FIELDS, "metric", name),
        check_datum(decl, fixture, "metric", name),
        check_corrective(decl, fixture, correction_event, "metric", name),
        check_dual_test(decl, "metric", name),
    ]
    return green_report("metric", name, results)
