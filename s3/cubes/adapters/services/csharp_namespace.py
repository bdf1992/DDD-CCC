"""
csharp_namespace — extract the `namespace X.Y.Z` declaration from C# source.

Authored for the `csharp_unity` adapter.

Handles both C# namespace forms:
  - block-scoped: `namespace Foo.Bar { ... }`
  - file-scoped (C# 10+): `namespace Foo.Bar;`

Returns the first declared namespace dotted name, or None if the file
declares none (global namespace / top-level statements). A C# file may
legally declare multiple namespaces in one file; this service returns the
first one encountered, which is the common case. Adapters wanting all
declared namespaces can call `extract_all_namespaces`.
"""
from __future__ import annotations

import re
from typing import Optional

from s3.cubes.adapters.services._seed import ServiceMetadata


SERVICE = ServiceMetadata(
    name="csharp_namespace",
    purpose="Extract the `namespace X.Y.Z` declaration from C# source.",
    inputs="body: str — C# source text",
    outputs="Optional[str] — first declared dotted namespace, or None",
    example='extract_namespace("namespace Foo.Bar { }") == "Foo.Bar"',
    used_by=("csharp-unity",),
)

# Match `namespace X.Y.Z` at line start (with leading whitespace allowed),
# followed by either `;` (file-scoped) or `{` (block-scoped) or end-of-line
# (some formatters put `{` on the next line).
_NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_.]*)\s*(?:[;{]|$)",
    re.MULTILINE,
)


def extract_namespace(body: str) -> Optional[str]:
    """Return the first declared namespace in the body, or None."""
    m = _NAMESPACE_RE.search(body)
    return m.group(1).strip() if m else None


def extract_all_namespaces(body: str) -> list[str]:
    """Return every declared namespace in the body, in appearance order."""
    return [m.group(1).strip() for m in _NAMESPACE_RE.finditer(body)]


def run_self_test() -> dict:
    cases: list[tuple[str, str, Optional[str]]] = [
        ("empty", "", None),
        ("no_namespace", "using System;\npublic class X {}", None),
        ("block_scoped",
         "namespace Foo.Bar\n{\n    public class X {}\n}", "Foo.Bar"),
        ("block_brace_same_line",
         "namespace Foo.Bar {\n    public class X {}\n}", "Foo.Bar"),
        ("file_scoped",
         "namespace Foo.Bar;\npublic class X {}", "Foo.Bar"),
        ("deep_dot",
         "namespace MyProject.Models.Core\n{\n}",
         "MyProject.Models.Core"),
        ("namespace_in_comment",
         "// namespace Commented.Out\nnamespace Real.One\n{}", "Real.One"),
        ("leading_using",
         "using System;\nusing UnityEngine;\nnamespace Foo\n{}", "Foo"),
    ]
    failures: list[dict] = []
    for name, body, want in cases:
        got = extract_namespace(body)
        if got != want:
            failures.append({"name": name, "got": got, "want": want})

    # Also test extract_all_namespaces on a multi-namespace file.
    multi = "namespace A\n{\n}\nnamespace B\n{\n}"
    all_got = extract_all_namespaces(multi)
    if all_got != ["A", "B"]:
        failures.append({"name": "extract_all_namespaces_multi",
                         "got": all_got, "want": ["A", "B"]})

    total = len(cases) + 1
    return {
        "passed": not failures,
        "summary": (f"ok: {total} assertions" if not failures
                    else f"failed: {len(failures)}/{total} "
                         f"[{', '.join(f['name'] for f in failures)}]"),
        "failures": failures,
    }


if __name__ == "__main__":
    print(run_self_test())
