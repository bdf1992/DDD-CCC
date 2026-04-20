"""
ProfileCard — assembled from adapter output, not new extraction.

Reads already-emitted SourceRecord metadata: Greenfield Profile primitive rows,
Obsidian frontmatter, markdown H1s, package metadata fields carried in
`record.metadata`. Assembles a canonical Profile Card without re-scanning or
re-extracting.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if TYPE_CHECKING:
    from s3.cubes.adapters.base import SourceRecord


@dataclass
class ProfileCard:
    """Assembled identity surface of a project.

    Every field draws from adapter output. Empty fields mean the adapter
    didn't expose them — NOT that the installer fabricated a value.
    """
    name: Optional[str] = None
    primary_purpose: Optional[str] = None
    domain: Optional[str] = None
    maturity: dict = field(default_factory=dict)  # counts by source_type
    stakeholders: list[str] = field(default_factory=list)
    dominant_language: Optional[str] = None
    provenance: list[str] = field(default_factory=list)  # which records contributed

    def is_minimally_complete(self) -> bool:
        """A Profile Card is minimally complete if it has at least a name."""
        return bool(self.name)

    def evidence_count(self) -> int:
        return len(self.provenance)


def assemble_profile_card(candidates: list) -> ProfileCard:
    """Assemble a ProfileCard from a candidate pool (SourceRecord list).

    Draws from:
      - Greenfield `profile` primitive rows (if any).
      - Greenfield `source` primitive rows (fallback for name/purpose).
      - README H1 in markdown/obsidian records.
      - package metadata in the canonical metadata dict (name, description).
      - source_type distribution for maturity counts.
      - extension distribution for dominant_language.
    """
    card = ProfileCard()

    # Priority 1: Greenfield profile primitive (if present).
    gf_profiles = [c for c in candidates if c.source_type == "greenfield_profile"]
    if gf_profiles:
        top = gf_profiles[0]
        raw = (top.metadata or {}).get("raw", {})
        card.name = card.name or raw.get("name") or top.title
        card.primary_purpose = (card.primary_purpose
                                or raw.get("purpose")
                                or raw.get("description"))
        card.domain = card.domain or raw.get("domain")
        if isinstance(raw.get("stakeholders"), list):
            card.stakeholders = [str(x) for x in raw["stakeholders"]]
        card.provenance.append(top.source_id)

    # Priority 2: README (first markdown with title "README" or URI ending README.md).
    if card.name is None or card.primary_purpose is None:
        readme_candidates = [
            c for c in candidates
            if c.source_type in ("markdown", "obsidian_note")
            and (c.title or "").lower().startswith("readme")
            or str(c.uri).replace("\\", "/").lower().endswith("readme.md")
        ]
        for r in readme_candidates:
            card.name = card.name or (r.title if r.title and not r.title.lower().startswith("readme") else None)
            if card.primary_purpose is None:
                first_para = _first_paragraph(r.body)
                if first_para:
                    card.primary_purpose = first_para[:240]
            card.provenance.append(r.source_id)
            if card.name and card.primary_purpose:
                break

    # Priority 3: package metadata (pyproject / package.json / etc.) surfaced
    # through adapter canonical metadata. At v0 adapters don't extract this
    # explicitly, so we check the raw metadata dict for name/description fields.
    if card.name is None:
        for c in candidates:
            md = c.metadata or {}
            raw = md.get("raw") or {}
            name_guess = raw.get("name") or md.get("name")
            if name_guess:
                card.name = str(name_guess)
                card.provenance.append(c.source_id)
                break

    # Maturity: source_type distribution.
    type_counts = Counter(c.source_type for c in candidates)
    card.maturity = dict(type_counts)

    # Dominant language: extension distribution over code-like records.
    ext_counts: Counter = Counter()
    for c in candidates:
        md = c.metadata or {}
        ext = md.get("extension") or ""
        if ext and ext.startswith("."):
            ext_counts[ext] += 1
    if ext_counts:
        card.dominant_language = ext_counts.most_common(1)[0][0]

    return card


def _first_paragraph(body: str) -> str:
    """Return the first non-empty paragraph after any frontmatter / H1.

    Skips YAML frontmatter between `---` fences if present, skips blank lines,
    skips the H1 heading line, then returns the next paragraph (lines until a
    blank line). Empty string if no paragraph found.
    """
    if not body:
        return ""
    lines = body.splitlines()
    i = 0
    # Skip frontmatter
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1
    # Skip blank lines
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Skip H1 heading line if present
    if i < len(lines) and lines[i].strip().startswith("# "):
        i += 1
    # Skip blank lines
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Collect paragraph
    paragraph_lines: list[str] = []
    while i < len(lines) and lines[i].strip():
        paragraph_lines.append(lines[i].strip())
        i += 1
    return " ".join(paragraph_lines).strip()
