"""
RegencyAdapter — reads a regency-style `regencies/` directory.

A "Regency" is a bounded-work-session directory named `REGENCY-NNN-slug/`
containing one or more markdown files (`goal.md`, `pre-conditions.md`,
sometimes `guidance.md`, `improvements.md`, `eval.md`). Each directory is
one candidate unit; this adapter emits one SourceRecord per directory with
the concatenated body of all its markdown files.

Uses services:
  - regency_refs.extract_regency_refs → outbound_refs (REGENCY-NNN tokens)

source_type = "regency_folder".

Pressure claim: reveals *Regency dependency vacuums* — `REGENCY-NNN`
tokens referenced in one Regency's goal/pre-conditions with no
corresponding `REGENCY-NNN-*/` directory declared in the tree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRef, SourceRecord
from s3.cubes.adapters.services import extract_regency_refs


_REGENCY_DIR_RE = re.compile(r"^REGENCY-(\d{3})-(.+)$")


class RegencyAdapter:
    """Walks a `regencies/` directory, emitting one SourceRecord per REGENCY.

    Config:
        root    : path to the regencies/ dir (contains REGENCY-NNN-slug/ children).
        exclude : glob patterns to skip inside regency dirs (defaults skip nothing).
    """
    name = "regency"

    def __init__(
        self,
        root: Path | str,
        exclude: tuple[str, ...] = (),
    ):
        self.root = Path(root).resolve()
        self.exclude = tuple(exclude)

    def _iter_regency_dirs(self):
        if not self.root.exists():
            return
        for p in sorted(self.root.iterdir()):
            if not p.is_dir():
                continue
            if not _REGENCY_DIR_RE.match(p.name):
                continue
            yield p

    def _regency_from_dir(self, d: Path) -> Optional[str]:
        """Canonical REGENCY-NNN token derived from dir name."""
        m = _REGENCY_DIR_RE.match(d.name)
        if not m:
            return None
        return f"REGENCY-{m.group(1)}"

    def _slug_from_dir(self, d: Path) -> str:
        m = _REGENCY_DIR_RE.match(d.name)
        return m.group(2) if m else d.name

    def discover(self) -> list[SourceRef]:
        return [SourceRef(adapter=self.name, uri=str(p))
                for p in self._iter_regency_dirs()]

    def read(self, ref: SourceRef) -> SourceRecord:
        d = Path(ref.uri)
        regency = self._regency_from_dir(d) or d.name
        slug = self._slug_from_dir(d)

        md_files = sorted(d.glob("*.md"))
        parts: list[str] = []
        md_filenames: list[str] = []
        for md in md_files:
            rel = md.relative_to(d).as_posix()
            if any(Path(rel).match(pat) for pat in self.exclude):
                continue
            parts.append(f"<!-- {rel} -->\n" + md.read_text(encoding="utf-8", errors="replace"))
            md_filenames.append(rel)
        body = "\n\n".join(parts)

        # Extract cross-Regency refs, excluding self-references
        all_refs = extract_regency_refs(body)
        seen: set[str] = set()
        outbound: list[str] = []
        for r in all_refs:
            if r == regency:
                continue  # self-ref
            if r in seen:
                continue
            seen.add(r)
            outbound.append(r)

        stat_mtime = max((md.stat().st_mtime for md in md_files), default=0)
        modified_at = (
            datetime.fromtimestamp(stat_mtime, tz=timezone.utc).isoformat()
            if stat_mtime else datetime.now(tz=timezone.utc).isoformat()
        )

        return SourceRecord(
            source_id=ref.stable_id(),
            source_type="regency_folder",
            uri=str(d),
            title=f"{regency}: {slug}",
            body=body,
            metadata={
                "regency": regency,
                "slug": slug,
                "md_files": md_filenames,
                "n_md_files": len(md_filenames),
                "body_bytes": len(body),
                "modified_at": modified_at,
                "rel_path": d.relative_to(self.root).as_posix(),
            },
            version_hash=SourceRecord.fingerprint(body),
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            parent_refs=[str(self.root)],
            outbound_refs=outbound,
        )

    def changed_since(self, watermark: Optional[str]) -> list[SourceRef]:
        if watermark is None:
            return self.discover()
        try:
            wm = datetime.fromisoformat(watermark)
        except ValueError:
            return self.discover()
        out: list[SourceRef] = []
        for d in self._iter_regency_dirs():
            mtime_ts = max((md.stat().st_mtime for md in d.glob("*.md")), default=0)
            if mtime_ts == 0:
                continue
            mtime = datetime.fromtimestamp(mtime_ts, tz=timezone.utc)
            if mtime > wm:
                out.append(SourceRef(adapter=self.name, uri=str(d)))
        return out


# ============================================================================
# PROOF — the four proofs for RegencyAdapter.
# ============================================================================

@dataclass
class RegencyProofFixture:
    """Fixture bundle for the four proofs.

    adapter              : a RegencyAdapter instance pointed at a carved regency tree.
    whitelist_external   : set of REGENCY-NNN tokens treated as resolved
                           despite not having a directory (e.g., future work
                           planned but not yet directory-created).
    """
    adapter: "RegencyAdapter"
    whitelist_external: frozenset = frozenset()


def _records_for_fixture(fixture: RegencyProofFixture):
    a = fixture.adapter
    return [a.read(ref) for ref in a.discover()]


def _declared_regencies(records) -> set[str]:
    """Set of REGENCY-NNN declared by having a directory."""
    out: set[str] = set()
    for r in records:
        regency = (r.metadata or {}).get("regency")
        if regency:
            out.add(regency)
    return out


def _all_outbound(records) -> set[tuple[str, str]]:
    """(source_id, referenced REGENCY-NNN) pairs across all records."""
    pairs: set[tuple[str, str]] = set()
    for r in records:
        for ref in r.outbound_refs:
            pairs.add((r.source_id, ref))
    return pairs


def _compute_unresolved(records, whitelisted: frozenset = frozenset()) -> list[dict]:
    declared = _declared_regencies(records)
    pairs = _all_outbound(records)
    instances: list[dict] = []
    for source_id, ref in sorted(pairs):
        if ref in declared or ref in whitelisted:
            continue
        rec = next((r for r in records if r.source_id == source_id), None)
        if rec is None:
            continue
        instances.append({
            "name": "unresolved_regency_dep",
            "value": ref,
            "cell_refs": [source_id],
            "evidence": {
                "source_id": source_id,
                "uri": rec.uri,
                "referring_regency": (rec.metadata or {}).get("regency"),
                "extracted_from": "outbound_refs (REGENCY-NNN tokens)",
                "all_declared_at_observation": sorted(declared),
                "whitelist_at_observation": sorted(whitelisted),
            },
            "severity": "info",
            "recommended_action": (
                f"either create directory `REGENCY-{ref.split('-')[1]}-<slug>/` "
                f"or whitelist as external_reference"
            ),
        })
    return instances


def _run_pressure(fixture: RegencyProofFixture) -> dict:
    records = _records_for_fixture(fixture)
    wl = frozenset(fixture.whitelist_external or ())
    declared = _declared_regencies(records)
    pairs = _all_outbound(records)
    unresolved = sorted({ref for _, ref in pairs
                         if ref not in declared and ref not in wl})
    candidates_with_orphans = sorted({
        sid for sid, ref in pairs
        if ref not in declared and ref not in wl
    })
    return {
        "adapter_name": "regency",
        "cell_candidates": candidates_with_orphans,
        "witness": {
            "unresolved_regency_refs": unresolved,
            "n_records": len(records),
            "n_declared_regencies": len(declared),
            "n_outbound_pairs": len(pairs),
            "n_whitelisted": len(wl),
        },
        "pressure_kind": "regency_dependency_vacuum",
        "fires_at": "commit",
    }


def _run_datum(fixture: RegencyProofFixture) -> list[dict]:
    records = _records_for_fixture(fixture)
    wl = frozenset(fixture.whitelist_external or ())
    return _compute_unresolved(records, wl)


def _run_corrective(fixture: RegencyProofFixture, correction_event: dict) -> dict:
    records = _records_for_fixture(fixture)
    baseline_wl = frozenset(fixture.whitelist_external or ())
    new_terms = frozenset(correction_event.get("whitelist_external", ()))
    combined_wl = baseline_wl | new_terms
    before = len(_compute_unresolved(records, baseline_wl))
    after = len(_compute_unresolved(records, combined_wl))
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
            "RegencyAdapter reveals Regency dependency vacuums — "
            "`REGENCY-NNN` tokens referenced in one Regency's goal / pre-"
            "conditions with no corresponding REGENCY-NNN-* directory "
            "declared in the tree."
        ),
        pressure_runner=_run_pressure,
        datum_name="unresolved_regency_dep",
        datum_runner=_run_datum,
        corrective_runner=_run_corrective,
        code_tests_module="s3.cubes.adapters.tests.regency_test",
        skill_test_fixture="s3/cubes/skill_tests/fixtures/regency_mini/",
    )


PROOF = _build_proof()


# Default correction event consumed by the proof harness.
# Whitelisting REGENCY-999 drops the unresolved count 1→0 on the fixture.
DEFAULT_CORRECTION_EVENT = {"whitelist_external": ["REGENCY-999"]}
