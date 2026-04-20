"""
CSharpUnityAdapter — reads a Unity C# source tree.

Walks a root directory (typically a Unity project's `Assets/Scripts/`),
emits one SourceRecord per `.cs` file. Skips `.meta` sidecar files. Uses
services:
  - csharp_usings.extract_usings       → outbound_refs (dotted namespace refs)
  - csharp_namespace.extract_namespace → metadata.namespace

source_type = "csharp_source".

Pressure claim: reveals *unresolved internal-using vacuums* — `using
<internal_prefix>.X.Y;` declarations with no corresponding `namespace
<internal_prefix>.X.Y` declared anywhere in the tree. The internal
prefix is supplied at adapter init; defaults absent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRef, SourceRecord
from s3.cubes.adapters.services import extract_usings, extract_namespace


class CSharpUnityAdapter:
    """Walks a C# source tree, emitting one SourceRecord per `.cs` file.

    Config:
        root             : path to the source root (e.g. Assets/Scripts/).
        internal_prefix  : dotted namespace prefix that marks *internal*
                           references (e.g. the root namespace of your
                           project). Usings not starting with this prefix
                           are treated as external (stdlib / Unity / NuGet / etc.).
        exclude          : glob patterns to skip (defaults: .meta,
                           Library/, Logs/, obj/, bin/).
    """
    name = "csharp-unity"

    def __init__(
        self,
        root: Path | str,
        internal_prefix: str = "",
        exclude: tuple[str, ...] = (
            "**/*.meta",
            "Library/**",
            "Logs/**",
            "obj/**",
            "bin/**",
        ),
    ):
        self.root = Path(root).resolve()
        self.internal_prefix = internal_prefix
        self.exclude = tuple(exclude)

    def _iter_files(self):
        for p in self.root.rglob("*.cs"):
            rel = p.relative_to(self.root).as_posix()
            if any(Path(rel).match(pat) for pat in self.exclude):
                continue
            yield p

    def discover(self) -> list[SourceRef]:
        return [SourceRef(adapter=self.name, uri=str(p)) for p in self._iter_files()]

    def read(self, ref: SourceRef) -> SourceRecord:
        path = Path(ref.uri)
        body = path.read_text(encoding="utf-8", errors="replace")
        stat = path.stat()

        namespace = extract_namespace(body)
        usings = extract_usings(body)
        # Title = namespace-qualified file stem if available.
        title = f"{namespace}.{path.stem}" if namespace else path.stem

        return SourceRecord(
            source_id=ref.stable_id(),
            source_type="csharp_source",
            uri=str(path),
            title=title,
            body=body,
            metadata={
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "namespace": namespace,
                "usings": usings,
                "file_stem": path.stem,
                "extension": ".cs",
                "rel_path": path.relative_to(self.root).as_posix(),
            },
            version_hash=SourceRecord.fingerprint(body),
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            parent_refs=[str(path.parent.resolve())],
            outbound_refs=list(usings),
        )

    def changed_since(self, watermark: Optional[str]) -> list[SourceRef]:
        if watermark is None:
            return self.discover()
        try:
            wm = datetime.fromisoformat(watermark)
        except ValueError:
            return self.discover()
        out: list[SourceRef] = []
        for p in self._iter_files():
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if mtime > wm:
                out.append(SourceRef(adapter=self.name, uri=str(p)))
        return out


# ============================================================================
# PROOF — the four proofs for CSharpUnityAdapter.
# ============================================================================

@dataclass
class CSharpUnityProofFixture:
    """Fixture shape for the four proofs.

    adapter            : a CSharpUnityAdapter instance pointed at the carved fixture.
    whitelist_external : initial set of internally-prefixed namespaces treated as
                         resolved despite having no declaring file in the tree
                         (e.g. namespaces defined in an external DLL or NuGet).
    """
    adapter: "CSharpUnityAdapter"
    whitelist_external: frozenset = frozenset()


def _records_for_fixture(fixture: CSharpUnityProofFixture):
    a = fixture.adapter
    return [a.read(ref) for ref in a.discover()]


def _declared_namespaces(records) -> set[str]:
    """Set of `namespace X.Y` declared across all records' metadata."""
    out: set[str] = set()
    for r in records:
        ns = (r.metadata or {}).get("namespace")
        if ns:
            out.add(ns)
    return out


def _internal_usings(records, internal_prefix: str) -> set[tuple[str, str]]:
    """(source_id, dotted_using) pairs restricted to the internal prefix."""
    if not internal_prefix:
        return set()
    dot_prefix = internal_prefix + "."
    pairs: set[tuple[str, str]] = set()
    for r in records:
        for u in r.outbound_refs:
            if u == internal_prefix or u.startswith(dot_prefix):
                pairs.add((r.source_id, u))
    return pairs


def _compute_unresolved(records, internal_prefix: str,
                        whitelisted: frozenset = frozenset()) -> list[dict]:
    declared = _declared_namespaces(records)
    pairs = _internal_usings(records, internal_prefix)
    instances: list[dict] = []
    for source_id, using in sorted(pairs):
        if using in declared or using in whitelisted:
            continue
        # Recover the record for evidence
        rec = next((r for r in records if r.source_id == source_id), None)
        if rec is None:
            continue
        instances.append({
            "name": "unresolved_internal_using",
            "value": using,
            "cell_refs": [source_id],
            "evidence": {
                "source_id": source_id,
                "uri": rec.uri,
                "extracted_from": "outbound_refs (usings)",
                "declaring_namespace": (rec.metadata or {}).get("namespace"),
                "internal_prefix": internal_prefix,
                "all_declared_at_observation": sorted(declared),
                "whitelist_at_observation": sorted(whitelisted),
            },
            "severity": "info",
            "recommended_action": (
                f"either add a file declaring `namespace {using}` or "
                f"whitelist it as intentionally_external"
            ),
        })
    return instances


def _run_pressure(fixture: CSharpUnityProofFixture) -> dict:
    records = _records_for_fixture(fixture)
    internal = fixture.adapter.internal_prefix
    wl = frozenset(fixture.whitelist_external or ())
    declared = _declared_namespaces(records)
    pairs = _internal_usings(records, internal)
    unresolved = sorted({u for _, u in pairs if u not in declared and u not in wl})
    candidates_with_orphans = sorted({
        sid for sid, u in pairs if u not in declared and u not in wl
    })
    return {
        "adapter_name": "csharp-unity",
        "cell_candidates": candidates_with_orphans,
        "witness": {
            "unresolved_internal_usings": unresolved,
            "n_records": len(records),
            "n_declared_namespaces": len(declared),
            "n_internal_using_pairs": len(pairs),
            "n_whitelisted": len(wl),
            "internal_prefix": internal,
        },
        "pressure_kind": "internal_using_vacuum",
        "fires_at": "commit",
    }


def _run_datum(fixture: CSharpUnityProofFixture) -> list[dict]:
    records = _records_for_fixture(fixture)
    wl = frozenset(fixture.whitelist_external or ())
    return _compute_unresolved(records, fixture.adapter.internal_prefix, wl)


def _run_corrective(fixture: CSharpUnityProofFixture, correction_event: dict) -> dict:
    records = _records_for_fixture(fixture)
    internal = fixture.adapter.internal_prefix
    baseline_wl = frozenset(fixture.whitelist_external or ())
    new_terms = frozenset(correction_event.get("whitelist_external", ()))
    combined_wl = baseline_wl | new_terms
    before = len(_compute_unresolved(records, internal, baseline_wl))
    after = len(_compute_unresolved(records, internal, combined_wl))
    return {
        "before": before,
        "after": after,
        "whitelist_before": sorted(baseline_wl),
        "whitelist_after": sorted(combined_wl),
        "new_terms_applied": sorted(new_terms - baseline_wl),
    }


def _build_proof():
    from s3.cubes.proofs import ProofDeclaration
    return ProofDeclaration(
        pressure_claim=(
            "CSharpUnityAdapter reveals unresolved internal-using vacuums — "
            "`using <internal_prefix>.X.Y;` declarations with no corresponding "
            "`namespace <internal_prefix>.X.Y` declared in the source tree."
        ),
        pressure_runner=_run_pressure,
        datum_name="unresolved_internal_using",
        datum_runner=_run_datum,
        corrective_runner=_run_corrective,
        code_tests_module="s3.cubes.adapters.tests.csharp_unity_test",
        skill_test_fixture="s3/cubes/skill_tests/fixtures/csharp_unity_mini/",
    )


PROOF = _build_proof()


# Default correction event consumed by the proof harness (run_proofs).
# Whitelists a fixture-internal using so the corrective pattern produces a
# measurable before/after shift. The fixture's namespaces are rooted at
# "CatalystCore" — when running against your own tree, adjust the whitelist.
DEFAULT_CORRECTION_EVENT = {"whitelist_external": ["CatalystCore.Models.Data"]}
