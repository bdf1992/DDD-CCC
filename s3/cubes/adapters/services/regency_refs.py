"""
regency_refs — extract `REGENCY-NNN` cross-references from markdown bodies.

Authored for the `regency` adapter.

Regency folders use `REGENCY-\\d{3}` as their cross-reference token in
both frontmatter (`regency: REGENCY-001`) and body prose (*"REGENCY-001
must have reached acceptance"*). This service pulls the canonical
REGENCY-NNN form out of any text body, appearance-ordered, duplicates
preserved.

Shape-mirrors `csharp_usings` and `wikilink_extractor` — same service
contract, different token grammar. Per the `no refactor existing services
for a new variant` rule in services/README.md, this is authored alongside
rather than generalizing the two existing extractors.
"""
from __future__ import annotations

import re

from s3.cubes.adapters.services._seed import ServiceMetadata


SERVICE = ServiceMetadata(
    name="regency_refs",
    purpose="Extract REGENCY-NNN cross-reference tokens from markdown bodies.",
    inputs="body: str — markdown text that may contain REGENCY-\\d{3} tokens",
    outputs="list[str] — canonical tokens (e.g., 'REGENCY-001'), appearance order",
    example='extract_regency_refs("see REGENCY-001 and REGENCY-002") '
            '== ["REGENCY-001", "REGENCY-002"]',
    used_by=("regency",),
)

# Match REGENCY-NNN exactly (3-digit form). Word-boundary anchored so
# inline code like `REGENCY-001-slug` still extracts the REGENCY-001 prefix.
_REGENCY_RE = re.compile(r"\bREGENCY-(\d{3})\b")


def extract_regency_refs(body: str) -> list[str]:
    """Pull REGENCY-NNN tokens from a body. Pure, no I/O."""
    return [f"REGENCY-{m.group(1)}" for m in _REGENCY_RE.finditer(body)]


def run_self_test() -> dict:
    cases: list[tuple[str, str, list[str]]] = [
        ("empty", "", []),
        ("plain_no_match", "some markdown body", []),
        ("one_ref", "see REGENCY-001", ["REGENCY-001"]),
        ("two_refs",
         "REGENCY-001 depends on REGENCY-002",
         ["REGENCY-001", "REGENCY-002"]),
        ("dup_preserved",
         "REGENCY-001 and REGENCY-001 again",
         ["REGENCY-001", "REGENCY-001"]),
        ("frontmatter_extract",
         "---\nregency: REGENCY-007\n---",
         ["REGENCY-007"]),
        ("within_slug_still_caught",
         "the REGENCY-003-orphan folder",
         ["REGENCY-003"]),
        ("not_matched_2_digit",
         "REGENCY-99 is malformed, REGENCY-099 is ok",
         ["REGENCY-099"]),
        ("not_matched_4_digit",
         "REGENCY-1000 is malformed, REGENCY-100 is ok",
         ["REGENCY-100"]),  # "REGENCY-100" matches, then "0" continues past \b
        ("case_sensitive",
         "regency-001 lowercase not matched",
         []),
    ]
    failures: list[dict] = []
    for name, body, want in cases:
        got = extract_regency_refs(body)
        if got != want:
            failures.append({"name": name, "got": got, "want": want})
    return {
        "passed": not failures,
        "summary": (f"ok: {len(cases)} assertions" if not failures
                    else f"failed: {len(failures)}/{len(cases)} "
                         f"[{', '.join(f['name'] for f in failures)}]"),
        "failures": failures,
    }


if __name__ == "__main__":
    print(run_self_test())
