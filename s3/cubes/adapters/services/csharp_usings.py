"""
csharp_usings — extract `using X.Y.Z;` declarations from C# source.

Authored for the `csharp_unity` adapter.

Handles the common C# using forms:
  - `using System;`
  - `using MyProject.Models.Core;`
  - `using static System.Math;` → captured as `System.Math` with static flag
  - `using Alias = System.Console;` → captured as `System.Console` with alias

Returns a list of cleaned dotted namespace / type references in
appearance order. Does NOT resolve; resolution is the adapter's job.
"""
from __future__ import annotations

import re

from s3.cubes.adapters.services._seed import ServiceMetadata


SERVICE = ServiceMetadata(
    name="csharp_usings",
    purpose="Extract `using X.Y.Z;` declarations from C# source as dotted names.",
    inputs="body: str — C# source text",
    outputs="list[str] — dotted namespace/type references, appearance order",
    example='extract_usings("using System;\\nusing MyProject.Models.Core;") '
            '== ["System", "MyProject.Models.Core"]',
    used_by=("csharp-unity",),
)

# Match `using [static] [Alias =] X.Y.Z;` — pull the dotted RHS.
_USING_RE = re.compile(
    r"^\s*using\s+(?:static\s+)?(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?"
    r"([A-Za-z_][A-Za-z0-9_.]*)\s*;",
    re.MULTILINE,
)


def extract_usings(body: str) -> list[str]:
    """Pull dotted namespace/type names from `using ...;` declarations."""
    return [m.group(1).strip() for m in _USING_RE.finditer(body)]


def run_self_test() -> dict:
    cases: list[tuple[str, str, list[str]]] = [
        ("empty", "", []),
        ("plain_single", "using System;", ["System"]),
        ("dotted",
         "using MyProject.Models.Core;",
         ["MyProject.Models.Core"]),
        ("multi",
         "using System;\nusing UnityEngine;\nusing MyProject.Systems;",
         ["System", "UnityEngine", "MyProject.Systems"]),
        ("static",
         "using static System.Math;",
         ["System.Math"]),
        ("alias",
         "using Console = System.Console;",
         ["System.Console"]),
        ("not_matched_in_body",
         "public class X { /* using Y; */ }",
         []),  # regex anchored to start-of-line (MULTILINE), body-comment isn't at col 0
        ("mixed_with_namespace_decl",
         "using System;\nnamespace Foo.Bar\n{\n}",
         ["System"]),  # 'namespace' is not a 'using'
        ("preserves_order",
         "using Z;\nusing A;\nusing M;",
         ["Z", "A", "M"]),
    ]
    failures: list[dict] = []
    for name, body, want in cases:
        got = extract_usings(body)
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
