"""
services — the pluginable-services library for adapter-design.

The library grows on-demand. When the adapter-design skill runs against a
new target repo and finds a source system the existing services don't
cover, the skill authors a new service module here — with its own SERVICE
declaration + run_self_test — and composes it into the generated adapter.

Seed: `_seed.py` — the `wikilink_extractor` service, lift-extracted from
`s3/cubes/adapters/obsidian_vault.py`. Demonstrates the service contract.

Discovery: each service module exposes module-level `SERVICE:
ServiceMetadata` + `run_self_test() -> dict`. The services library is
audited by the `adapter-design` skill at the start of each run.

Contract: see README.md.
"""
from s3.cubes.adapters.services._seed import (
    ServiceMetadata,
    SERVICE as WIKILINK_SERVICE,
    extract_wikilinks,
    run_self_test as wikilink_self_test,
)
from s3.cubes.adapters.services.csharp_usings import (
    SERVICE as CSHARP_USINGS_SERVICE,
    extract_usings,
)
from s3.cubes.adapters.services.csharp_namespace import (
    SERVICE as CSHARP_NAMESPACE_SERVICE,
    extract_namespace,
    extract_all_namespaces,
)
from s3.cubes.adapters.services.regency_refs import (
    SERVICE as REGENCY_REFS_SERVICE,
    extract_regency_refs,
)


# Registry — adapter-design appends here when it authors a new service.
# Keep this canonical: each entry = (module dotted path, SERVICE object).
REGISTRY: list[tuple[str, ServiceMetadata]] = [
    ("s3.cubes.adapters.services._seed", WIKILINK_SERVICE),
    ("s3.cubes.adapters.services.csharp_usings", CSHARP_USINGS_SERVICE),
    ("s3.cubes.adapters.services.csharp_namespace", CSHARP_NAMESPACE_SERVICE),
    ("s3.cubes.adapters.services.regency_refs", REGENCY_REFS_SERVICE),
]


def audit_library() -> dict:
    """Run every registered service's self-test. Return an aggregate report.

    adapter-design skill calls this at the top of each run: if any service
    fails its self-test, the library is not trustworthy and new adapter
    authoring halts until it's fixed.
    """
    import importlib
    results: list[dict] = []
    overall_passed = True
    for dotted, meta in REGISTRY:
        try:
            mod = importlib.import_module(dotted)
            fn = getattr(mod, "run_self_test", None)
            if fn is None:
                results.append({"service": meta.name, "passed": False,
                                "summary": f"{dotted} has no run_self_test"})
                overall_passed = False
                continue
            r = fn()
            results.append({
                "service": meta.name,
                "passed": bool(r.get("passed")),
                "summary": r.get("summary", ""),
                "failures": r.get("failures", []),
            })
            if not r.get("passed"):
                overall_passed = False
        except Exception as e:
            results.append({"service": meta.name, "passed": False,
                            "summary": f"exception: {type(e).__name__}: {e}"})
            overall_passed = False
    return {
        "passed": overall_passed,
        "n_services": len(REGISTRY),
        "n_green": sum(1 for r in results if r["passed"]),
        "results": results,
    }


__all__ = [
    "ServiceMetadata",
    "WIKILINK_SERVICE",
    "extract_wikilinks",
    "wikilink_self_test",
    "CSHARP_USINGS_SERVICE",
    "extract_usings",
    "CSHARP_NAMESPACE_SERVICE",
    "extract_namespace",
    "extract_all_namespaces",
    "REGENCY_REFS_SERVICE",
    "extract_regency_refs",
    "REGISTRY",
    "audit_library",
]
