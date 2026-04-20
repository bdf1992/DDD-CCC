"""
Dual test for CSharpUnityAdapter (Proof 4).

run()             — code TDD: exercise discover/read/outbound_refs against
                    the carved fixture, assert expected unresolved set.
run_skill_test()  — skill-vs-code agreement: reload adapter + PROOF + test
                    module from disk, rerun run().

Fixture expectations (see fixtures/csharp_unity_mini/README.md):
  - 4 .cs files, excludes .meta + Library/ + Logs/
  - 4 declared namespaces under CatalystCore.Sample.*
  - 2 unresolved internal usings: CatalystCore.Models.Data, CatalystCore.MissingModule
"""
from __future__ import annotations

import importlib
import traceback
from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from s3.cubes.adapters.csharp_unity import CSharpUnityAdapter


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "s3" / "cubes" / "skill_tests" / "fixtures" / "csharp_unity_mini"
INTERNAL_PREFIX = "CatalystCore"


def _collect(tests: list[tuple[str, bool, Any]]) -> dict:
    failures = [(name, detail) for name, ok, detail in tests if not ok]
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
        adapter = CSharpUnityAdapter(FIXTURE, internal_prefix=INTERNAL_PREFIX)
        refs = adapter.discover()
        records = [adapter.read(r) for r in refs]

        namespaces = {(r.metadata or {}).get("namespace") for r in records}
        namespaces.discard(None)
        all_usings = {u for r in records for u in r.outbound_refs}
        internal_usings = {u for u in all_usings
                           if u == INTERNAL_PREFIX
                           or u.startswith(INTERNAL_PREFIX + ".")}
        unresolved = internal_usings - namespaces

        expected_stems = {"Root", "Systems", "Orphan", "Clean"}
        stems = {(r.metadata or {}).get("file_stem") for r in records}
        expected_ns = {
            "CatalystCore.Sample",
            "CatalystCore.Sample.Systems",
            "CatalystCore.Sample.Orphan",
            "CatalystCore.Sample.Clean",
        }
        expected_unresolved = {
            "CatalystCore.Models.Data",
            "CatalystCore.MissingModule",
        }

        tests = [
            ("fixture exists",
             FIXTURE.exists(), str(FIXTURE)),
            ("adapter name",
             adapter.name == "csharp-unity", adapter.name),
            ("discover() returns 4 refs",
             len(refs) == 4, len(refs)),
            ("refs tagged csharp-unity",
             all(r.adapter == "csharp-unity" for r in refs),
             [r.adapter for r in refs]),
            ("all source_type csharp_source",
             all(r.source_type == "csharp_source" for r in records),
             [r.source_type for r in records]),
            ("all bodies non-empty",
             all(r.body for r in records), [len(r.body) for r in records]),
            ("all version_hash sha256:",
             all(r.version_hash.startswith("sha256:") for r in records),
             [r.version_hash[:12] for r in records]),
            ("file stems match",
             stems == expected_stems,
             {"got": sorted(s for s in stems if s),
              "want": sorted(expected_stems)}),
            ("declared namespaces match",
             namespaces == expected_ns,
             {"got": sorted(namespaces), "want": sorted(expected_ns)}),
            ("usings extracted",
             len(all_usings) >= 6,
             sorted(all_usings)),
            ("internal usings subset",
             INTERNAL_PREFIX + ".Models.Data" in internal_usings
             and INTERNAL_PREFIX + ".MissingModule" in internal_usings,
             sorted(internal_usings)),
            ("unresolved set matches",
             unresolved == expected_unresolved,
             {"got": sorted(unresolved),
              "want": sorted(expected_unresolved)}),
            ("metadata.namespace populated",
             all((r.metadata or {}).get("namespace") for r in records),
             [(r.metadata or {}).get("namespace") for r in records]),
            ("changed_since(None) returns 4",
             len(adapter.changed_since(None)) == 4,
             len(adapter.changed_since(None))),
        ]
        return _collect(tests)
    except Exception as e:
        return {"passed": False,
                "summary": f"exception in run(): {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}


def run_skill_test(fixture_path: str) -> dict:
    """Skill-vs-code agreement: reload adapter module + PROOF + rerun run()."""
    fp = Path(fixture_path)
    if not fp.exists():
        return {"passed": False,
                "summary": f"skill_test fixture missing: {fp}",
                "details": {}}
    try:
        import s3.cubes.adapters.csharp_unity as mod
        importlib.reload(mod)
        proof = getattr(mod, "PROOF", None)
        if proof is None:
            return {"passed": False,
                    "summary": "PROOF missing after reload",
                    "details": {}}
        proof_fields = [
            ("pressure_claim non-empty", bool(proof.pressure_claim)),
            ("datum_name == 'unresolved_internal_using'",
             proof.datum_name == "unresolved_internal_using"),
            ("pressure_runner callable", callable(proof.pressure_runner)),
            ("datum_runner callable", callable(proof.datum_runner)),
            ("corrective_runner callable", callable(proof.corrective_runner)),
            ("code_tests_module set",
             proof.code_tests_module == "s3.cubes.adapters.tests.csharp_unity_test"),
            ("skill_test_fixture matches",
             Path(proof.skill_test_fixture).resolve() == fp.resolve()),
        ]
        missing = [n for n, ok in proof_fields if not ok]
        if missing:
            return {"passed": False,
                    "summary": f"PROOF incomplete after reload: {missing}",
                    "details": {"proof_fields": proof_fields}}
        import s3.cubes.adapters.tests.csharp_unity_test as tm
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
