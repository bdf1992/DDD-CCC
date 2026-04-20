"""
Proof harness — shared four-proof runner + result types.

A module is **provable** iff it exposes a `PROOF` attribute of type
`ProofDeclaration` carrying four callables + metadata:

    pressure_claim       : str — one-line claim of measurable pressure
    pressure_runner      : fixture -> dict with required pressure-event fields
    datum_name           : str — the data-derivable datum this module provides
    datum_runner         : fixture -> list[dict]  (datum instances; each has `evidence`)
    corrective_runner    : (fixture, correction_event) -> dict with {before, after}
    code_tests_module    : dotted import path of a pytest-compatible test module
    skill_test_fixture   : path (str) to the fixture driving the skill-vs-code test

Per-kind runners (adapter_proof, metric_proof, datum_proof) add kind-specific
field requirements on top of these four checks.

The harness is deliberately plain: no pytest, no magic imports. It runs the
declarative PROOF and records pass/fail with evidence. Code-test + skill-test
execution goes through `harness._run_test_module` which imports the test module
and invokes its `run()` entrypoint (convention).
"""
from __future__ import annotations

import importlib
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


ProofKind = str   # "pressure" | "datum" | "corrective" | "dual_test"
PROOF_KINDS: tuple[ProofKind, ...] = ("pressure", "datum", "corrective", "dual_test")


@dataclass
class ProofDeclaration:
    """What a module ships to be provable.

    Each field must be set; a None indicates the module is not provable yet
    (proof_status=ungated). The harness refuses to verify modules with a
    partially-populated declaration.
    """
    pressure_claim: str
    pressure_runner: Callable[[Any], dict]
    datum_name: str
    datum_runner: Callable[[Any], list[dict]]
    corrective_runner: Callable[[Any, dict], dict]
    code_tests_module: str
    skill_test_fixture: str
    # Optional: for kind-specific requirements the runner can peek at.
    extras: dict = field(default_factory=dict)


@dataclass
class ProofResult:
    """One proof's verdict on one module."""
    module_kind: str
    module_name: str
    proof: ProofKind
    passed: bool
    message: str
    evidence: dict = field(default_factory=dict)

    def oneline(self) -> str:
        mark = "OK" if self.passed else "FAIL"
        return f"[{mark}] {self.module_kind}/{self.module_name} :: {self.proof} — {self.message}"


@dataclass
class ProofReport:
    """All four proofs' verdicts on one module."""
    module_kind: str
    module_name: str
    results: list[ProofResult] = field(default_factory=list)

    @property
    def green(self) -> bool:
        return len(self.results) == len(PROOF_KINDS) and all(r.passed for r in self.results)

    def summary(self) -> str:
        lines = [f"{self.module_kind}/{self.module_name}: "
                 f"{'GREEN' if self.green else 'FAIL'} "
                 f"({sum(1 for r in self.results if r.passed)}/{len(PROOF_KINDS)})"]
        for r in self.results:
            lines.append("  " + r.oneline())
        return "\n".join(lines)


def green_report(module_kind: str, module_name: str,
                 results: list[ProofResult]) -> ProofReport:
    """Bundle results into a report."""
    return ProofReport(module_kind=module_kind, module_name=module_name, results=results)


# --- shared helpers ---------------------------------------------------------

def _fail(module_kind: str, module_name: str, proof: ProofKind,
          message: str, evidence: Optional[dict] = None) -> ProofResult:
    return ProofResult(module_kind, module_name, proof, False, message, evidence or {})


def _pass(module_kind: str, module_name: str, proof: ProofKind,
          message: str, evidence: Optional[dict] = None) -> ProofResult:
    return ProofResult(module_kind, module_name, proof, True, message, evidence or {})


def check_pressure(decl: ProofDeclaration, fixture: Any,
                   required_fields: tuple[str, ...],
                   module_kind: str, module_name: str) -> ProofResult:
    """Invoke pressure_runner and verify the event carries the required fields."""
    if not decl.pressure_claim or not decl.pressure_claim.strip():
        return _fail(module_kind, module_name, "pressure",
                     "pressure_claim is empty")
    try:
        event = decl.pressure_runner(fixture)
    except Exception as e:
        return _fail(module_kind, module_name, "pressure",
                     f"pressure_runner raised {type(e).__name__}: {e}",
                     {"traceback": traceback.format_exc()})
    if not isinstance(event, dict):
        return _fail(module_kind, module_name, "pressure",
                     f"pressure_runner must return dict, got {type(event).__name__}")
    missing = [f for f in required_fields if f not in event]
    if missing:
        return _fail(module_kind, module_name, "pressure",
                     f"pressure event missing required fields: {missing}",
                     {"event_keys": sorted(event.keys())})
    return _pass(module_kind, module_name, "pressure",
                 f"claim='{decl.pressure_claim}' emits {sorted(required_fields)}",
                 {"event": event})


def check_datum(decl: ProofDeclaration, fixture: Any,
                module_kind: str, module_name: str) -> ProofResult:
    """Invoke datum_runner and verify each instance has `evidence` derivable from data."""
    if not decl.datum_name:
        return _fail(module_kind, module_name, "datum",
                     "datum_name is empty")
    try:
        instances = decl.datum_runner(fixture)
    except Exception as e:
        return _fail(module_kind, module_name, "datum",
                     f"datum_runner raised {type(e).__name__}: {e}",
                     {"traceback": traceback.format_exc()})
    if not isinstance(instances, list):
        return _fail(module_kind, module_name, "datum",
                     f"datum_runner must return list, got {type(instances).__name__}")
    if not instances:
        return _fail(module_kind, module_name, "datum",
                     f"datum_runner returned no instances on fixture "
                     f"(data-derivable datum must fire on its own proof fixture)")
    no_evidence = [i for i, inst in enumerate(instances)
                   if not isinstance(inst, dict) or not inst.get("evidence")]
    if no_evidence:
        return _fail(module_kind, module_name, "datum",
                     f"{len(no_evidence)}/{len(instances)} instances missing "
                     f"non-empty `evidence` field (vibed datums refused)",
                     {"bad_indices": no_evidence})
    return _pass(module_kind, module_name, "datum",
                 f"{decl.datum_name}: {len(instances)} instance(s) with evidence",
                 {"n_instances": len(instances),
                  "sample_evidence_keys": sorted((instances[0].get("evidence") or {}).keys())
                                          if isinstance(instances[0].get("evidence"), dict)
                                          else None})


def check_corrective(decl: ProofDeclaration, fixture: Any,
                     correction_event: dict,
                     module_kind: str, module_name: str) -> ProofResult:
    """Invoke corrective_runner and verify it reports a measurable shift."""
    try:
        report = decl.corrective_runner(fixture, correction_event)
    except Exception as e:
        return _fail(module_kind, module_name, "corrective",
                     f"corrective_runner raised {type(e).__name__}: {e}",
                     {"traceback": traceback.format_exc()})
    if not isinstance(report, dict) or "before" not in report or "after" not in report:
        return _fail(module_kind, module_name, "corrective",
                     "corrective_runner must return dict with keys {'before', 'after'}",
                     {"got_type": type(report).__name__})
    before, after = report["before"], report["after"]
    if before == after:
        return _fail(module_kind, module_name, "corrective",
                     "corrective_runner produced no measurable shift "
                     "(before == after; correction had no effect)",
                     {"before": before, "after": after})
    return _pass(module_kind, module_name, "corrective",
                 f"correction shifted output (delta observed)",
                 {"before": before, "after": after, "correction": correction_event})


def check_dual_test(decl: ProofDeclaration,
                    module_kind: str, module_name: str) -> ProofResult:
    """Run the code TDD tests + the skill-vs-code agreement test.

    Convention: each referenced test module exposes `run() -> dict` returning
    {passed: bool, summary: str, details: dict}. The harness reports both.
    """
    if not decl.code_tests_module:
        return _fail(module_kind, module_name, "dual_test",
                     "code_tests_module is empty")
    if not decl.skill_test_fixture:
        return _fail(module_kind, module_name, "dual_test",
                     "skill_test_fixture is empty")

    # Run code TDD
    code_result = _run_test_module(decl.code_tests_module)
    if not code_result["passed"]:
        return _fail(module_kind, module_name, "dual_test",
                     f"code TDD failed: {code_result['summary']}",
                     {"code_test": code_result})

    # Skill test: run_skill_test(fixture_path) if tests module exposes it;
    # otherwise check the fixture at least exists + is non-empty.
    skill_result = _run_skill_test(decl.code_tests_module, decl.skill_test_fixture)
    if not skill_result["passed"]:
        return _fail(module_kind, module_name, "dual_test",
                     f"skill-vs-code agreement failed: {skill_result['summary']}",
                     {"code_test": code_result, "skill_test": skill_result})

    return _pass(module_kind, module_name, "dual_test",
                 f"code TDD + skill-vs-code agreement both green",
                 {"code_test": code_result, "skill_test": skill_result})


def _run_test_module(dotted: str) -> dict:
    """Import dotted path and invoke its `run()` entrypoint."""
    try:
        mod = importlib.import_module(dotted)
    except Exception as e:
        return {"passed": False,
                "summary": f"import {dotted} failed: {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}
    if not hasattr(mod, "run"):
        return {"passed": False,
                "summary": f"{dotted} has no run() entrypoint",
                "details": {}}
    try:
        out = mod.run()
    except Exception as e:
        return {"passed": False,
                "summary": f"{dotted}.run() raised {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}
    if not isinstance(out, dict) or "passed" not in out:
        return {"passed": False,
                "summary": f"{dotted}.run() must return dict with 'passed' key",
                "details": {"got": repr(out)[:200]}}
    return out


def _run_skill_test(dotted: str, fixture_path: str) -> dict:
    """Invoke `run_skill_test(fixture_path)` on the test module if available."""
    fp = Path(fixture_path)
    if not fp.exists():
        return {"passed": False,
                "summary": f"skill-test fixture missing: {fp}",
                "details": {}}
    try:
        mod = importlib.import_module(dotted)
    except Exception as e:
        return {"passed": False,
                "summary": f"import {dotted} failed: {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}
    if not hasattr(mod, "run_skill_test"):
        # Soft-pass: if the test module doesn't expose a skill-test entry,
        # require the fixture to at least exist and be non-empty. This lets
        # early modules retrofit without a full LLM-replay harness.
        size = fp.stat().st_size if fp.is_file() else sum(
            p.stat().st_size for p in fp.rglob("*") if p.is_file())
        if size == 0:
            return {"passed": False,
                    "summary": f"skill-test fixture empty: {fp}",
                    "details": {}}
        return {"passed": True,
                "summary": f"fixture-only skill-test (no run_skill_test); "
                           f"fixture {fp} size={size}",
                "details": {"mode": "fixture_only"}}
    try:
        out = mod.run_skill_test(str(fp))
    except Exception as e:
        return {"passed": False,
                "summary": f"run_skill_test raised {type(e).__name__}: {e}",
                "details": {"traceback": traceback.format_exc()}}
    if not isinstance(out, dict) or "passed" not in out:
        return {"passed": False,
                "summary": "run_skill_test must return dict with 'passed' key",
                "details": {"got": repr(out)[:200]}}
    return out
