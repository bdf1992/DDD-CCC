"""
Dual test for RegencyAdapter (Proof 4).

run()             — code TDD: exercise discover/read/outbound_refs against
                    the carved fixture, assert expected unresolved set.
run_skill_test()  — skill-vs-code agreement: reload adapter + PROOF + test
                    module from disk, rerun run().

Fixture expectations (see fixtures/regency_mini/README.md):
  - 3 REGENCY-NNN-slug directories
  - 3 declared regencies: REGENCY-001, REGENCY-002, REGENCY-003
  - 1 unresolved cross-ref: REGENCY-999 (from REGENCY-003-orphan)
"""
from __future__ import annotations

import importlib
import traceback
from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from s3.cubes.adapters.regency import RegencyAdapter


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "s3" / "cubes" / "skill_tests" / "fixtures" / "regency_mini"


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
        adapter = RegencyAdapter(FIXTURE)
        refs = adapter.discover()
        records = [adapter.read(r) for r in refs]

        regencies = {(r.metadata or {}).get("regency") for r in records}
        regencies.discard(None)
        all_outbound = {ref for r in records for ref in r.outbound_refs}
        unresolved = all_outbound - regencies

        expected_regencies = {"REGENCY-001", "REGENCY-002", "REGENCY-003"}
        expected_outbound_superset = {"REGENCY-001", "REGENCY-999"}
        expected_unresolved = {"REGENCY-999"}

        tests: list[tuple[str, bool, Any]] = [
            ("fixture exists", FIXTURE.exists(), str(FIXTURE)),
            ("adapter name",
             adapter.name == "regency", adapter.name),
            ("discover returns 3 dirs",
             len(refs) == 3, len(refs)),
            ("refs tagged regency",
             all(r.adapter == "regency" for r in refs),
             [r.adapter for r in refs]),
            ("source_type regency_folder",
             all(r.source_type == "regency_folder" for r in records),
             [r.source_type for r in records]),
            ("declared regencies match",
             regencies == expected_regencies,
             {"got": sorted(regencies), "want": sorted(expected_regencies)}),
            ("titles formatted REGENCY-NNN: slug",
             all(r.title.startswith("REGENCY-") and ": " in r.title
                 for r in records),
             [r.title for r in records]),
            ("outbound refs include expected crosses",
             expected_outbound_superset.issubset(all_outbound),
             sorted(all_outbound)),
            ("unresolved set == {REGENCY-999}",
             unresolved == expected_unresolved,
             {"got": sorted(unresolved), "want": sorted(expected_unresolved)}),
            ("REGENCY-003-orphan is the only record with unresolved refs",
             sum(1 for r in records
                 if set(r.outbound_refs) - regencies) == 1,
             [r.title for r in records
              if set(r.outbound_refs) - regencies]),
            ("all bodies non-empty",
             all(r.body for r in records), [len(r.body) for r in records]),
            ("version_hash sha256:",
             all(r.version_hash.startswith("sha256:") for r in records),
             [r.version_hash[:12] for r in records]),
            ("metadata.n_md_files == 2 each",
             all((r.metadata or {}).get("n_md_files") == 2 for r in records),
             [(r.metadata or {}).get("n_md_files") for r in records]),
            ("changed_since(None) returns 3",
             len(adapter.changed_since(None)) == 3,
             len(adapter.changed_since(None))),
            ("self-refs filtered (REGENCY-001 not in its own outbound)",
             "REGENCY-001" not in next(
                 r.outbound_refs for r in records
                 if (r.metadata or {}).get("regency") == "REGENCY-001"
             ),
             [r.outbound_refs for r in records
              if (r.metadata or {}).get("regency") == "REGENCY-001"]),
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
        import s3.cubes.adapters.regency as mod
        importlib.reload(mod)
        proof = getattr(mod, "PROOF", None)
        if proof is None:
            return {"passed": False,
                    "summary": "PROOF missing after reload",
                    "details": {}}
        proof_fields = [
            ("pressure_claim non-empty", bool(proof.pressure_claim)),
            ("datum_name == 'unresolved_regency_dep'",
             proof.datum_name == "unresolved_regency_dep"),
            ("pressure_runner callable", callable(proof.pressure_runner)),
            ("datum_runner callable", callable(proof.datum_runner)),
            ("corrective_runner callable", callable(proof.corrective_runner)),
            ("code_tests_module set",
             proof.code_tests_module == "s3.cubes.adapters.tests.regency_test"),
            ("skill_test_fixture matches",
             Path(proof.skill_test_fixture).resolve() == fp.resolve()),
        ]
        missing = [n for n, ok in proof_fields if not ok]
        if missing:
            return {"passed": False,
                    "summary": f"PROOF incomplete after reload: {missing}",
                    "details": {"proof_fields": proof_fields}}
        import s3.cubes.adapters.tests.regency_test as tm
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
