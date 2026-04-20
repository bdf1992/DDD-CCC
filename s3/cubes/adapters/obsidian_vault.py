"""
ObsidianVaultAdapter — reads an Obsidian vault.

Same surface as FilesystemMarkdownAdapter but understands:
  - YAML frontmatter (between leading `---` fences)
  - Wikilinks: [[Target]], [[Target|alias]], [[Target#heading]]
  - Obsidian's vault root marker (.obsidian/ directory)

Emits source_type = "obsidian_note".
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRef, SourceRecord, SourceAdapter


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][\w/-]*)")


class ObsidianVaultAdapter:
    """Walks an Obsidian vault, emitting notes with wikilinks and frontmatter.

    Config:
        vault_root : path to the vault (directory containing `.obsidian/`, or any dir).
        exclude    : glob patterns to skip (defaults include .obsidian, .trash).
    """
    name = "obsidian"

    def __init__(
        self,
        vault_root: Path | str,
        exclude: tuple[str, ...] = (".obsidian/**", ".trash/**"),
    ):
        self.vault_root = Path(vault_root).resolve()
        self.exclude = tuple(exclude)

    def _iter_files(self):
        for p in self.vault_root.rglob("*.md"):
            rel = p.relative_to(self.vault_root).as_posix()
            if any(Path(rel).match(pat) for pat in self.exclude):
                continue
            yield p

    def discover(self) -> list[SourceRef]:
        return [SourceRef(adapter=self.name, uri=str(p)) for p in self._iter_files()]

    def read(self, ref: SourceRef) -> SourceRecord:
        path = Path(ref.uri)
        body = path.read_text(encoding="utf-8", errors="replace")
        stat = path.stat()

        frontmatter, stripped_body = _split_frontmatter(body)
        title = frontmatter.get("title") or _extract_h1(stripped_body) or path.stem
        wikilinks = _extract_wikilinks(stripped_body)
        tags = _extract_tags(stripped_body) + _frontmatter_tags(frontmatter)
        parent = str(path.parent.resolve())

        return SourceRecord(
            source_id=ref.stable_id(),
            source_type="obsidian_note",
            uri=str(path),
            title=title,
            body=body,
            metadata={
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "frontmatter": frontmatter,
                "tags": sorted(set(tags)),
                "vault_path": path.relative_to(self.vault_root).as_posix(),
                "extension": ".md",
            },
            version_hash=SourceRecord.fingerprint(body),
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            parent_refs=[parent],
            outbound_refs=wikilinks,
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


def _split_frontmatter(body: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_without_frontmatter). Lightweight YAML parsing.

    Handles scalars, quoted strings, lists (`- item`), and `key: value` pairs.
    Does not pull in pyyaml — keeps dep-light for now.
    """
    m = _FRONTMATTER_RE.match(body)
    if not m:
        return {}, body
    fm_text = m.group(1)
    rest = body[m.end():]
    return _parse_mini_yaml(fm_text), rest


def _parse_mini_yaml(text: str) -> dict:
    out: dict = {}
    current_key: Optional[str] = None
    current_list: Optional[list] = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and current_key is not None:
            if current_list is None:
                current_list = []
                out[current_key] = current_list
            current_list.append(line.lstrip()[2:].strip().strip('"').strip("'"))
            continue
        if ":" in line:
            current_list = None
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if not val:
                current_key = key
                out[key] = None
                continue
            current_key = key
            if val.startswith("[") and val.endswith("]"):
                items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
                out[key] = items
            else:
                out[key] = val.strip('"').strip("'")
    return out


def _extract_h1(body: str) -> Optional[str]:
    m = _HEADING_RE.search(body)
    return m.group(1).strip() if m else None


def _extract_wikilinks(body: str) -> list[str]:
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(body)]


def _extract_tags(body: str) -> list[str]:
    return [m.group(1) for m in _TAG_RE.finditer(body)]


def _frontmatter_tags(fm: dict) -> list[str]:
    t = fm.get("tags")
    if isinstance(t, list):
        return [str(x) for x in t]
    if isinstance(t, str):
        return [s.strip() for s in t.split(",") if s.strip()]
    return []


# ============================================================================
# PROOF — the four proofs for ObsidianVaultAdapter.
#
# Pressure: ObsidianVaultAdapter reveals unresolved-wikilink vacuums — terms
# referenced in notes but not mapped to any cell. Cell-grounded: each
# unresolved target is a candidate vacuum *adjacent to* the notes that
# reference it.
# Datum: unresolved_wikilink_term. Computed from data as
#   (outbound_refs across all records) \ (note stems ∪ whitelisted external).
# Corrective: user whitelists a wikilink target as external_only; subsequent
# datum runs exclude it. Harness verifies before != after.
# Dual test: s3.cubes.adapters.tests.obsidian_vault_test with run() +
# run_skill_test(fixture).
# ============================================================================

from dataclasses import dataclass as _dc


@_dc
class ObsidianProofFixture:
    """Fixture shape for the four proofs.

    adapter            : an ObsidianVaultAdapter instance pointed at the vault.
    whitelist_external : initial set of externally-resolved wikilink targets.
    """
    adapter: "ObsidianVaultAdapter"
    whitelist_external: frozenset = frozenset()


def _records_for_fixture(fixture: ObsidianProofFixture):
    a = fixture.adapter
    return [a.read(ref) for ref in a.discover()]


def _note_stems(records) -> set[str]:
    stems: set[str] = set()
    for r in records:
        vp = (r.metadata or {}).get("vault_path", "")
        if vp:
            stems.add(Path(vp).stem)
        if r.title:
            stems.add(r.title)
    return stems


def _compute_unresolved(records, stems: set[str],
                        whitelisted: frozenset = frozenset()) -> list[dict]:
    instances: list[dict] = []
    for r in records:
        for link in r.outbound_refs:
            if link in stems or link in whitelisted:
                continue
            instances.append({
                "name": "unresolved_wikilink_term",
                "value": link,
                "cell_refs": [r.source_id],
                "evidence": {
                    "source_id": r.source_id,
                    "uri": r.uri,
                    "extracted_from": "outbound_refs",
                    "note_title": r.title,
                    "all_stems_at_observation": sorted(stems),
                    "whitelist_at_observation": sorted(whitelisted),
                },
                "severity": "info",
                "recommended_action": (
                    f"create note for [[{link}]] or mark external_only "
                    f"via adapter corrective"
                ),
            })
    return instances


def _run_pressure(fixture: ObsidianProofFixture) -> dict:
    records = _records_for_fixture(fixture)
    stems = _note_stems(records)
    wl = frozenset(fixture.whitelist_external or ())
    all_links = {link for r in records for link in r.outbound_refs}
    unresolved = sorted(all_links - stems - wl)
    candidates_with_orphans = sorted({
        r.source_id for r in records
        if any(link not in stems and link not in wl for link in r.outbound_refs)
    })
    return {
        "adapter_name": "obsidian",
        "cell_candidates": candidates_with_orphans,
        "witness": {
            "unresolved_terms": unresolved,
            "n_records": len(records),
            "n_note_stems": len(stems),
            "n_whitelisted": len(wl),
        },
        "pressure_kind": "citation_vacuum",
        "fires_at": "commit",
    }


def _run_datum(fixture: ObsidianProofFixture) -> list[dict]:
    records = _records_for_fixture(fixture)
    stems = _note_stems(records)
    wl = frozenset(fixture.whitelist_external or ())
    return _compute_unresolved(records, stems, wl)


def _run_corrective(fixture: ObsidianProofFixture, correction_event: dict) -> dict:
    records = _records_for_fixture(fixture)
    stems = _note_stems(records)
    baseline_wl = frozenset(fixture.whitelist_external or ())
    new_terms = frozenset(correction_event.get("whitelist_external", ()))
    combined_wl = baseline_wl | new_terms
    before = len(_compute_unresolved(records, stems, baseline_wl))
    after = len(_compute_unresolved(records, stems, combined_wl))
    return {
        "before": before,
        "after": after,
        "whitelist_before": sorted(baseline_wl),
        "whitelist_after": sorted(combined_wl),
        "new_terms_applied": sorted(new_terms - baseline_wl),
    }


# Lazy PROOF construction — imports from proofs lazily to avoid circular deps
# if a downstream module imports this at module load time.
def _build_proof():
    from s3.cubes.proofs import ProofDeclaration
    return ProofDeclaration(
        pressure_claim=(
            "ObsidianVaultAdapter reveals unresolved-wikilink vacuums — terms "
            "referenced in notes but not mapped to any cell."
        ),
        pressure_runner=_run_pressure,
        datum_name="unresolved_wikilink_term",
        datum_runner=_run_datum,
        corrective_runner=_run_corrective,
        code_tests_module="s3.cubes.adapters.tests.obsidian_vault_test",
        skill_test_fixture="s3/cubes/skill_tests/fixtures/obsidian_vault_mini/",
    )


PROOF = _build_proof()


# Default correction event consumed by the proof harness (demo_proofs).
# Whitelisting `wikipedia-external` drops the unresolved-term count from 3→2.
DEFAULT_CORRECTION_EVENT = {"whitelist_external": ["wikipedia-external"]}

