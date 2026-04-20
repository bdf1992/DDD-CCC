"""
Link normalization — canonicalize outbound_refs across adapter flavors.

Different adapters emit links in different conventions:
  - Markdown: `[label](path.md)` or `[label](path.md#heading)`
  - Obsidian: `[[Target]]`, `[[Target#heading]]`, `[[Target|alias]]`
  - Greenfield: explicit id strings or prior_hash chains

This module canonicalizes them into a small set of link classes so downstream
consumers (placement engine, datum families that read outbound_refs) don't
have to care about per-adapter syntax.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedLink:
    """A canonicalized outbound reference.

    kind: "path" | "wikilink" | "greenfield_id" | "url" | "other"
    target: the raw target string (already stripped of fragments/aliases)
    fragment: optional heading/section reference ("" if none)
    """
    kind: str
    target: str
    fragment: str = ""


def normalize_links(raw_refs: list[str], source_type: str) -> list[NormalizedLink]:
    """Classify and clean each raw outbound ref based on its shape + source_type."""
    out: list[NormalizedLink] = []
    for raw in raw_refs:
        if not raw:
            continue
        ref = raw.strip()
        if ref.startswith(("http://", "https://")):
            out.append(NormalizedLink(kind="url", target=ref, fragment=""))
            continue
        if "#" in ref and not ref.startswith("#"):
            t, frag = ref.split("#", 1)
        else:
            t, frag = ref, ""
        if source_type == "obsidian_note" or _looks_like_wikilink(raw):
            out.append(NormalizedLink(kind="wikilink", target=t.strip(), fragment=frag.strip()))
            continue
        if source_type.startswith("greenfield_"):
            out.append(NormalizedLink(kind="greenfield_id", target=t.strip(), fragment=frag.strip()))
            continue
        if t.endswith((".md", ".py", ".txt", ".json", ".yml", ".yaml")) or "/" in t:
            out.append(NormalizedLink(kind="path", target=t.strip(), fragment=frag.strip()))
            continue
        out.append(NormalizedLink(kind="other", target=t.strip(), fragment=frag.strip()))
    return out


def _looks_like_wikilink(raw: str) -> bool:
    """Heuristic: not-a-path, not-a-url, no extension, no leading slash."""
    return not (raw.startswith(("/", "http", ".")) or raw.endswith((".md", ".py", ".txt")))
