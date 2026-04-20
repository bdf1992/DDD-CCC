"""
run_proofs — the four-proof harness runner.

Runs the four-proof harness against every module flagged as `proof_status:
ungated` (or `green`) in `.claude/skills/_manifest.yaml`, and reports
pass/fail per proof per module. Writes witness artifacts to `.cube/reports/`.

Also invoked by the `cube proofs` CLI subcommand.

Run:
    python -m s3.cubes.run_proofs
    # or equivalently:
    cube proofs
"""
from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from s3.cubes.manifest import load_manifest, reality_check
from s3.cubes.proofs import verify_adapter, verify_metric


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / ".claude" / "skills" / "_manifest.yaml"
SKILLS_DIR = ROOT / ".claude" / "skills"
WITNESS_DIR = ROOT / ".cube" / "reports"
WITNESS_DIR.mkdir(parents=True, exist_ok=True)


def _build_adapter_fixture(entry, adapter):
    """Construct the per-adapter fixture shape from its module's conventions."""
    mod = importlib.import_module(entry.module)
    # Convention: adapter module exposes a `<AdapterClass>ProofFixture` or
    # a module-level `_proof_fixture(adapter) -> fixture` helper.
    builder = getattr(mod, "_proof_fixture", None)
    if builder is not None:
        return builder(adapter)
    # Fall back to the <Name>ProofFixture dataclass in the adapter module.
    for attr_name in dir(mod):
        if attr_name.endswith("ProofFixture"):
            cls = getattr(mod, attr_name)
            try:
                return cls(adapter=adapter)
            except TypeError:
                continue
    raise RuntimeError(f"no proof fixture builder for {entry.qualname()}")


def _instantiate_adapter(entry):
    """Instantiate the adapter against its skill-test fixture path.

    Honors manifest `init_kwargs` (e.g. `internal_prefix` for csharp-unity).
    """
    mod = importlib.import_module(entry.module)
    cls = getattr(mod, entry.class_name)
    proof = getattr(mod, "PROOF", None)
    if proof is None:
        raise RuntimeError(f"{entry.qualname()} has no module-level PROOF")
    fixture_path = ROOT / proof.skill_test_fixture
    kwargs = entry.extras.get("init_kwargs") or {}
    return cls(fixture_path, **kwargs)


def _build_metric_fixture(entry):
    """Construct the per-metric fixture from its module's conventions.

    Convention: metric's `skill_test_fixture` path contains a Python module
    named `fixture.py` that exposes `build_fixture() -> <ProofFixture>`.
    """
    mod = importlib.import_module(entry.module)
    proof = getattr(mod, "PROOF", None)
    if proof is None:
        raise RuntimeError(f"{entry.qualname()} has no module-level PROOF")
    fixture_path = ROOT / proof.skill_test_fixture
    # Import the fixture builder module by turning the path into a dotted name.
    dotted = ".".join(fixture_path.relative_to(ROOT).parts)
    builder_mod = importlib.import_module(dotted + ".fixture")
    return builder_mod.build_fixture()


def run_metric_proofs(manifest) -> list[tuple[Any, Any]]:
    """Return list of (ModuleEntry, ProofReport) for metric modules."""
    out: list[tuple[Any, Any]] = []
    for entry in manifest.by_kind("metrics"):
        mod = importlib.import_module(entry.module)
        if not hasattr(mod, "PROOF"):
            out.append((entry, None))
            continue
        try:
            fixture = _build_metric_fixture(entry)
        except Exception as e:
            # Report as a failure entry rather than crashing.
            from s3.cubes.proofs.harness import _fail, ProofReport
            name = entry.name
            out.append((entry, ProofReport(
                module_kind="metric", module_name=name,
                results=[_fail("metric", name, "pressure",
                               f"fixture builder failed: "
                               f"{type(e).__name__}: {e}")],
            )))
            continue
        correction_event = (
            getattr(fixture, "correction_event", None)
            or getattr(mod, "DEFAULT_CORRECTION_EVENT", None)
            or {}
        )
        report = verify_metric(mod, fixture, correction_event)
        out.append((entry, report))
    return out


def run_adapter_proofs(manifest) -> list[tuple[Any, Any]]:
    """Return list of (ModuleEntry, ProofReport)."""
    out: list[tuple[Any, Any]] = []
    for entry in manifest.by_kind("adapters"):
        mod = importlib.import_module(entry.module)
        if not hasattr(mod, "PROOF"):
            # Ungated and un-retrofit: skip with an info report
            out.append((entry, None))
            continue
        adapter = _instantiate_adapter(entry)
        fixture = _build_adapter_fixture(entry, adapter)
        # Correction event precedence:
        #   1. fixture attribute `correction_event` (builder-injected)
        #   2. adapter module attribute DEFAULT_CORRECTION_EVENT
        #   3. empty event → corrective proof will fail, surfacing the gap
        correction_event = (
            getattr(fixture, "correction_event", None)
            or getattr(mod, "DEFAULT_CORRECTION_EVENT", None)
            or {}
        )
        report = verify_adapter(adapter, fixture, correction_event)
        out.append((entry, report))
    return out


def _render(runs) -> str:
    lines: list[str] = []
    lines.append("# Proof Report")
    lines.append("")
    lines.append(f"Observed at: {datetime.now(tz=timezone.utc).isoformat()}")
    lines.append("")
    green_count = 0
    ungated_count = 0
    fail_count = 0
    for entry, report in runs:
        if report is None:
            ungated_count += 1
            lines.append(f"## {entry.qualname()} — ungated (no PROOF on module)")
            lines.append("")
            continue
        if report.green:
            green_count += 1
        else:
            fail_count += 1
        lines.append(f"## {entry.qualname()} — "
                     f"{'GREEN' if report.green else 'FAIL'}")
        lines.append("")
        lines.append("```")
        lines.append(report.summary())
        lines.append("```")
        lines.append("")
    lines.insert(2, f"**Summary**: {green_count} green · "
                    f"{fail_count} fail · {ungated_count} ungated")
    lines.insert(3, "")
    return "\n".join(lines)


def main() -> int:
    print(f"loading manifest: {MANIFEST_PATH}")
    m = load_manifest(MANIFEST_PATH)
    print(f"  instance={m.instance} fingerprint={m.fingerprint()[:22]}…")

    anomalies = reality_check(m, SKILLS_DIR, module_importable=True)
    if anomalies:
        print(f"\nreality_check: {len(anomalies)} anomalies (continuing):")
        for a in anomalies:
            print(f"  - {a}")
    else:
        print("reality_check: clean")

    print("\nrunning adapter proofs:")
    adapter_runs = run_adapter_proofs(m)
    for entry, report in adapter_runs:
        if report is None:
            print(f"  [--] {entry.qualname()}: ungated (no PROOF on module)")
            continue
        mark = "OK" if report.green else "FAIL"
        print(f"  [{mark}] {entry.qualname()}: "
              f"{sum(1 for r in report.results if r.passed)}/"
              f"{len(report.results)} proofs")
        if not report.green:
            for r in report.results:
                if not r.passed:
                    print(f"        - {r.proof}: {r.message}")

    print("\nrunning metric proofs:")
    metric_runs = run_metric_proofs(m)
    for entry, report in metric_runs:
        if report is None:
            print(f"  [--] {entry.qualname()}: ungated (no PROOF on module)")
            continue
        mark = "OK" if report.green else "FAIL"
        print(f"  [{mark}] {entry.qualname()}: "
              f"{sum(1 for r in report.results if r.passed)}/"
              f"{len(report.results)} proofs")
        if not report.green:
            for r in report.results:
                if not r.passed:
                    print(f"        - {r.proof}: {r.message}")

    runs = adapter_runs + metric_runs

    # Write witness + JSON summary
    witness_md = WITNESS_DIR / "proofs.md"
    witness_md.write_text(_render(runs), encoding="utf-8")

    summary_json = WITNESS_DIR / "proofs_summary.json"
    summary_json.write_text(json.dumps({
        "manifest_fingerprint": m.fingerprint(),
        "observed_at": datetime.now(tz=timezone.utc).isoformat(),
        "modules": [
            {
                "qualname": e.qualname(),
                "proof_status": e.proof_status,
                "report": (
                    None if r is None else {
                        "green": r.green,
                        "results": [
                            {"proof": x.proof, "passed": x.passed,
                             "message": x.message}
                            for x in r.results
                        ],
                    }
                ),
            }
            for e, r in runs
        ],
    }, indent=2), encoding="utf-8")

    print(f"\nwitness: {witness_md.relative_to(ROOT)}")
    print(f"summary: {summary_json.relative_to(ROOT)}")

    green = sum(1 for _, r in runs if r is not None and r.green)
    fail = sum(1 for _, r in runs if r is not None and not r.green)
    ungated = sum(1 for _, r in runs if r is None)
    print(f"\ntotals: {green} green · {fail} fail · {ungated} ungated")
    # Acceptance: at least one adapter green + zero fails.
    if fail > 0:
        return 1
    if green < 1:
        print("acceptance NOT met: no green adapter proofs yet")
        return 2
    print("acceptance met: ≥1 adapter fully proven, no failing proofs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
