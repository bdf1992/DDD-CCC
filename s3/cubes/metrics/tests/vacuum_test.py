"""
Dual test for VacuumMetric (Proof 4).

run()            — code TDD: exercise measure() against the fixture IR,
                   assert scalars + cell_readings shape + expected vacuum count.
run_skill_test() — skill-vs-code agreement: reload metric + PROOF + test
                   module from disk, rerun run().
"""
from __future__ import annotations

import importlib
import traceback
from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from s3.cubes.metrics.vacuum import VacuumMetric
from s3.cubes.skill_tests.fixtures.vacuum_metric_mini.fixture import (
    build_fixture,
    expected_vacuum_count,
)


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "s3" / "cubes" / "skill_tests" / "fixtures" / "vacuum_metric_mini"


def _collect(tests: list[tuple[str, bool, Any]]) -> dict:
    failures = [(n, d) for n, ok, d in tests if not ok]
    return {
        "passed": not failures,
        "summary": (f"ok: {len(tests)} assertions"
                    if not failures
                    else f"failed: {len(failures)}/{len(tests)} "
                         f"[{', '.join(n for n, _ in failures)}]"),
        "details": {
            "n_assertions": len(tests),
            "failures": [{"name": n, "detail": str(d)[:500]} for n, d in failures],
        },
    }


def run() -> dict:
    try:
        fixture = build_fixture()
        metric = VacuumMetric()
        result = metric.measure(fixture.ir)

        expected_vac = expected_vacuum_count(fixture)
        total_cells = sum(len(cs) for cs in fixture.ir.cube.cells_by_rank.values())

        tests: list[tuple[str, bool, Any]] = [
            ("fixture dir exists", FIXTURE.exists(), str(FIXTURE)),
            ("metric name 'vacuum'",
             metric.name == "vacuum", metric.name),
            ("fires_at contains 'ingest'",
             "ingest" in metric.fires_at, sorted(metric.fires_at)),
            ("MetricResult.name matches",
             result.name == "vacuum", result.name),
            ("scalars has vacuum_count",
             "vacuum_count" in result.scalars, result.scalars),
            ("vacuum_count matches expectation",
             result.scalars["vacuum_count"] == expected_vac,
             {"got": result.scalars["vacuum_count"], "want": expected_vac}),
            ("per-rank scalars present",
             all(f"vacuum_rank_{r}" in result.scalars
                 for r in fixture.ir.cube.cells_by_rank),
             [k for k in result.scalars if k.startswith("vacuum_rank_")]),
            ("cell_readings size == vacuum_count",
             len(result.cell_readings) == result.scalars["vacuum_count"],
             {"cr": len(result.cell_readings),
              "vc": result.scalars["vacuum_count"]}),
            ("each cell_reading has rank + is_vacuum",
             all("rank" in v and v.get("is_vacuum") is True
                 for v in result.cell_readings.values()),
             list(result.cell_readings.values())[:3]),
            ("summary non-empty",
             bool(result.summary), result.summary),
            ("no cube case — graceful",
             VacuumMetric().measure(type("FakeIR", (), {
                 "cube": None,
                 "cells_with_placements": lambda self: set(),
             })()).scalars["vacuum_count"] == 0, True),
            ("total cells == placed + vacuum",
             len(fixture.ir.cells_with_placements())
             + result.scalars["vacuum_count"] == total_cells,
             {"placed": len(fixture.ir.cells_with_placements()),
              "vacuum": result.scalars["vacuum_count"],
              "total": total_cells}),
        ]
        return _collect(tests)
    except Exception as e:
        return {"passed": False,
                "summary": f"exception in run(): {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}


def run_skill_test(fixture_path: str) -> dict:
    fp = Path(fixture_path)
    if not fp.exists():
        return {"passed": False,
                "summary": f"skill_test fixture missing: {fp}",
                "details": {}}
    try:
        import s3.cubes.metrics.vacuum as mod
        importlib.reload(mod)
        proof = getattr(mod, "PROOF", None)
        if proof is None:
            return {"passed": False,
                    "summary": "PROOF missing after reload",
                    "details": {}}
        proof_fields = [
            ("pressure_claim non-empty", bool(proof.pressure_claim)),
            ("datum_name == 'vacuum_cell'",
             proof.datum_name == "vacuum_cell"),
            ("pressure_runner callable", callable(proof.pressure_runner)),
            ("datum_runner callable", callable(proof.datum_runner)),
            ("corrective_runner callable", callable(proof.corrective_runner)),
            ("code_tests_module set",
             proof.code_tests_module == "s3.cubes.metrics.tests.vacuum_test"),
            ("skill_test_fixture matches",
             Path(proof.skill_test_fixture).resolve() == fp.resolve()),
        ]
        missing = [n for n, ok in proof_fields if not ok]
        if missing:
            return {"passed": False,
                    "summary": f"PROOF incomplete after reload: {missing}",
                    "details": {"proof_fields": proof_fields}}
        import s3.cubes.metrics.tests.vacuum_test as tm
        importlib.reload(tm)
        r = tm.run()
        if not r["passed"]:
            return {"passed": False,
                    "summary": f"post-reload code tests fail: {r['summary']}",
                    "details": {"code_result": r}}
        return {"passed": True,
                "summary": f"skill-vs-code agreement green ({r['summary']})",
                "details": {"code_result": r, "proof_fields": proof_fields}}
    except Exception as e:
        return {"passed": False,
                "summary": f"exception in run_skill_test: {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}


if __name__ == "__main__":
    print("=== run() ===")
    r1 = run()
    print(f"passed={r1['passed']} summary={r1['summary']}")
    if not r1["passed"]:
        import json
        print(json.dumps(r1["details"], indent=2, default=str))
    print("\n=== run_skill_test ===")
    r2 = run_skill_test(str(FIXTURE))
    print(f"passed={r2['passed']} summary={r2['summary']}")
