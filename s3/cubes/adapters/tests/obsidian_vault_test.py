"""
Dual test for ObsidianVaultAdapter (Proof 4).

run()              — code TDD: exercise discover/read/outbound_refs against
                     the mini fixture and assert shape.
run_skill_test()   — skill-vs-code agreement: re-runs run() after reloading
                     the adapter module from disk, verifying the protocol
                     described in adapter-design/SKILL.md produces a module
                     whose code tests still pass.

Both entrypoints return {"passed": bool, "summary": str, "details": dict}.
"""
from __future__ import annotations

import importlib
import traceback
from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from s3.cubes.adapters.obsidian_vault import ObsidianVaultAdapter


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "s3" / "cubes" / "skill_tests" / "fixtures" / "obsidian_vault_mini"


def _collect_assertions(tests: list[tuple[str, bool, Any]]) -> dict:
    failures = [(name, detail) for name, ok, detail in tests if not ok]
    return {
        "passed": not failures,
        "summary": ("ok: " + str(len(tests)) + " assertions"
                    if not failures
                    else f"failed: {len(failures)}/{len(tests)} "
                         f"[{', '.join(n for n, _ in failures)}]"),
        "details": {
            "n_assertions": len(tests),
            "failures": [{"name": n, "detail": str(d)[:500]} for n, d in failures],
        },
    }


def run() -> dict:
    """Code TDD against the mini fixture."""
    try:
        adapter = ObsidianVaultAdapter(FIXTURE)
        refs = adapter.discover()
        records = [adapter.read(r) for r in refs]

        stems = set()
        titles = set()
        outbound = set()
        for r in records:
            vp = (r.metadata or {}).get("vault_path", "")
            if vp:
                stems.add(Path(vp).stem)
            if r.title:
                titles.add(r.title)
            outbound.update(r.outbound_refs)

        expected_stems = {"index", "signal", "entropy", "README"}
        expected_unresolved = {"MISSING_GLOSSARY", "MISSING_CHANNEL",
                               "wikipedia-external"}
        actual_unresolved = outbound - stems

        tests = [
            ("fixture exists",
             FIXTURE.exists(),
             str(FIXTURE)),
            ("adapter name is 'obsidian'",
             adapter.name == "obsidian",
             adapter.name),
            ("discover() returns 4 refs",
             len(refs) == 4,
             len(refs)),
            ("each ref is an obsidian SourceRef",
             all(r.adapter == "obsidian" for r in refs),
             [r.adapter for r in refs]),
            ("each read() returns source_type 'obsidian_note'",
             all(r.source_type == "obsidian_note" for r in records),
             [r.source_type for r in records]),
            ("each record has a non-None body",
             all(r.body for r in records),
             [len(r.body) for r in records]),
            ("each record has version_hash starting with sha256:",
             all(r.version_hash.startswith("sha256:") for r in records),
             [r.version_hash[:12] for r in records]),
            ("each record has observed_at ISO8601-ish",
             all("T" in r.observed_at for r in records),
             [r.observed_at for r in records]),
            ("note stems match expectations",
             stems == expected_stems,
             {"got": sorted(stems), "want": sorted(expected_stems)}),
            ("titles are non-empty",
             all(t for t in titles),
             sorted(titles)),
            ("outbound_refs extracted (wikilinks)",
             len(outbound) >= 6,
             sorted(outbound)),
            ("unresolved set matches expected",
             actual_unresolved == expected_unresolved,
             {"got": sorted(actual_unresolved),
              "want": sorted(expected_unresolved)}),
            ("frontmatter parsed on at least one record",
             any((r.metadata or {}).get("frontmatter") for r in records),
             [bool((r.metadata or {}).get("frontmatter")) for r in records]),
            ("changed_since(None) returns all refs",
             len(adapter.changed_since(None)) == 4,
             len(adapter.changed_since(None))),
        ]
        return _collect_assertions(tests)
    except Exception as e:
        return {"passed": False,
                "summary": f"exception in run(): {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}


def run_skill_test(fixture_path: str) -> dict:
    """Skill-vs-code agreement: reload the adapter module from source and
    rerun the code tests. If the module on disk has drifted from what the
    adapter-design skill describes (ten-step protocol producing a
    SourceAdapter + PROOF), the reload + rerun will fail.

    A fuller skill replay (LLM authors the adapter from scratch against the
    fixture and re-runs the tests) is a later upgrade; the minimum bar here
    is: the code as-shipped survives a reload + rerun against the fixture
    named in PROOF.
    """
    fp = Path(fixture_path)
    if not fp.exists():
        return {"passed": False,
                "summary": f"skill_test fixture missing: {fp}",
                "details": {}}
    try:
        # Reload the adapter module + the proofs module, then rerun code tests.
        import s3.cubes.adapters.obsidian_vault as mod
        importlib.reload(mod)
        # PROOF must exist after reload
        proof = getattr(mod, "PROOF", None)
        if proof is None:
            return {"passed": False,
                    "summary": "after reload, PROOF attribute missing on "
                               "s3.cubes.adapters.obsidian_vault",
                    "details": {}}
        proof_fields = [
            ("pressure_claim non-empty", bool(proof.pressure_claim)),
            ("datum_name non-empty", bool(proof.datum_name)),
            ("pressure_runner callable", callable(proof.pressure_runner)),
            ("datum_runner callable", callable(proof.datum_runner)),
            ("corrective_runner callable", callable(proof.corrective_runner)),
            ("code_tests_module set",
             proof.code_tests_module == "s3.cubes.adapters.tests.obsidian_vault_test"),
            ("skill_test_fixture matches",
             Path(proof.skill_test_fixture).resolve() == fp.resolve()),
        ]
        missing = [name for name, ok in proof_fields if not ok]
        if missing:
            return {"passed": False,
                    "summary": f"PROOF declaration incomplete after reload: "
                               f"{missing}",
                    "details": {"proof_fields": proof_fields}}
        # Rerun code tests via module reload — not the in-memory function,
        # the freshly-loaded one.
        import s3.cubes.adapters.tests.obsidian_vault_test as tm
        importlib.reload(tm)
        code_result = tm.run()
        if not code_result["passed"]:
            return {"passed": False,
                    "summary": f"after reload, code tests fail: "
                               f"{code_result['summary']}",
                    "details": {"code_result": code_result}}
        return {"passed": True,
                "summary": "skill-vs-code agreement: PROOF intact after reload, "
                           f"code tests pass ({code_result['summary']})",
                "details": {"code_result": code_result,
                            "proof_fields": proof_fields}}
    except Exception as e:
        return {"passed": False,
                "summary": f"exception in run_skill_test: "
                           f"{type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}


if __name__ == "__main__":
    print("=== run() ===")
    r1 = run()
    print(f"passed={r1['passed']} summary={r1['summary']}")
    print("\n=== run_skill_test ===")
    r2 = run_skill_test(str(FIXTURE))
    print(f"passed={r2['passed']} summary={r2['summary']}")
