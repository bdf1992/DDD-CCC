"""
Seed service — wikilink_extractor.

The smallest complete example of what a service in
`s3/cubes/adapters/services/` IS. Demonstrates the five required properties:

  1. Pure function (no I/O; string in → list[str] out)
  2. Typed inputs + typed outputs
  3. Module-level `SERVICE: ServiceMetadata`
  4. `run_self_test() -> dict`
  5. Does one thing; composes with others; does not orchestrate

Lift-extracted from `s3/cubes/adapters/obsidian_vault.py`. The Obsidian
adapter keeps its inline wikilink regex — this service is a reusable mirror,
not a refactor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceMetadata:
    """Contract declaration every service ships at module level.

    name     : short lowercase identifier, unique in the library
    purpose  : one-line description of what this service does
    inputs   : shape description of what callers pass in
    outputs  : shape description of what the service returns
    example  : inline example of invocation + expected output
    used_by  : tuple of adapter names that import this service
               (updated whenever an adapter wires it in)
    """
    name: str
    purpose: str
    inputs: str
    outputs: str
    example: str
    used_by: tuple[str, ...] = field(default_factory=tuple)


_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")


SERVICE = ServiceMetadata(
    name="wikilink_extractor",
    purpose="Pull Obsidian-style wikilink targets out of a markdown-ish body.",
    inputs="body: str — text that may contain [[Target]] / [[Target#h]] / [[Target|alias]]",
    outputs="list[str] — target stems in appearance order (duplicates preserved)",
    example='extract_wikilinks("see [[foo]] and [[bar|alt]]") == ["foo", "bar"]',
    used_by=("obsidian",),
)


def extract_wikilinks(body: str) -> list[str]:
    """Pull wikilink targets from a body string. Pure, no I/O."""
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(body)]


def run_self_test() -> dict:
    """Self-test hook — services library audits call this before adapter runs.

    Return shape: {"passed": bool, "summary": str, "failures": list[dict]}.
    """
    cases = [
        ("empty", "", []),
        ("plain", "no links here", []),
        ("one_link", "see [[foo]]", ["foo"]),
        ("heading", "see [[foo#header]]", ["foo"]),
        ("alias", "see [[foo|alt]]", ["alt-not-picked"]),  # alias is NOT the target
        ("dup_preserved", "[[x]] [[x]]", ["x", "x"]),
        ("mixed", "[[a]] then [[b#h]] then [[c|alt]]", ["a", "b", "c"]),
        ("nested_brackets", "[[foo]] and [inner] text", ["foo"]),
    ]
    # Fix case 'alias' — the alias test above captured 'alt-not-picked' as a
    # sentinel; actual expected is ["foo"].
    cases[4] = ("alias", "see [[foo|alt]]", ["foo"])

    failures: list[dict] = []
    for name, body, want in cases:
        got = extract_wikilinks(body)
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
