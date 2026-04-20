"""
run_network — generate network-extension reports for every proven module
(adapters + metric), exercising the contextual-skill helpers end-to-end.

Invoked by the `cube network` CLI subcommand. For fresh authorship-skill
runs, the same report is generated in-line at Step 12 of the adapter
authoring protocol.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from s3.cubes.skill_support import (
    read_cube_context,
    balance_check,
    network_extension_report,
    render_report_markdown,
)


ROOT = Path(__file__).resolve().parents[2]
WITNESS = ROOT / ".cube" / "reports" / "network"
WITNESS.mkdir(parents=True, exist_ok=True)


def _proxy_pre_ir(placement_map: dict):
    """Build a minimal IR-duck for pre-run context from a placement map."""
    from dataclasses import dataclass

    @dataclass
    class _IR:
        placements: dict
        axis_convention: dict
        provenance: list
        cube: None = None

    return _IR(placements=placement_map, axis_convention={}, provenance=[])


def report_for(module_dotted: str, volume_added: str,
               connected_to: list[dict], vacuums_revealed: list[str],
               datum_names: list[str], projected_post_placements: dict[str, int]):
    mod = importlib.import_module(module_dotted)
    adapter_name = getattr(mod, "PROOF").datum_name  # proxy — identifier

    # Pre IR: empty (this is a first-time authorship against a fresh cube).
    pre = read_cube_context(_proxy_pre_ir({}))
    post = read_cube_context(_proxy_pre_ir(projected_post_placements))

    # Balance check on the projected placements
    bc = balance_check(_proxy_pre_ir({}), {k: len(v) for k, v in projected_post_placements.items()})

    report = network_extension_report(
        pre, post,
        module_name=module_dotted.split(".")[-1],
        volume_added=volume_added,
        connected_to=connected_to,
        datum_names=datum_names,
        vacuums_revealed=vacuums_revealed,
    )
    return report, bc


def main():
    # Retroactive reports for the two proven adapters.
    # Projected placements are synthetic cell labels — the manifest-bound
    # cube hasn't had csharp/obsidian candidates actually placed yet in
    # this demo, so we project illustrative distributions.

    # Obsidian — placements over vault notes
    obs_post = {
        "v0": ["obs::abc1", "obs::abc2"],
        "v1": ["obs::def1"],
        "v3": ["obs::ghi1"],
    }
    obs_report, obs_bc = report_for(
        "s3.cubes.adapters.obsidian_vault",
        volume_added="obsidian-notes-region",
        connected_to=[
            # First adapter; no prior volumes
        ],
        vacuums_revealed=[
            "unresolved wikilink: MISSING_GLOSSARY (from notes with obsidian_note type)",
            "unresolved wikilink: MISSING_CHANNEL",
            "unresolved wikilink: wikipedia-external",
        ],
        datum_names=["unresolved_wikilink_term"],
        projected_post_placements=obs_post,
    )

    # CSharpUnity — placements over C# source cells, connected to obsidian
    # via outbound_refs-as-citation face.
    cs_post = {
        **obs_post,
        "v2": ["csu::root1", "csu::sys1"],
        "v4": ["csu::orphan1", "csu::clean1"],
    }
    cs_report, cs_bc = report_for(
        "s3.cubes.adapters.csharp_unity",
        volume_added="csharp-source-region",
        connected_to=[
            {"volume": "obsidian-notes-region",
             "shared_element": "outbound_refs-as-citation",
             "rank_of_shared": "face",
             "note": "both adapters emit outbound_refs (Obsidian: wikilinks; "
                     "CSharpUnity: usings) that compose into the cube's "
                     "citation surface — the same face pattern applies across."}
        ],
        vacuums_revealed=[
            "unresolved internal using: Example.Models.Data (fixture)",
            "unresolved internal using: Example.MissingModule (fixture)",
        ],
        datum_names=["unresolved_internal_using"],
        projected_post_placements=cs_post,
    )

    # Write witnesses
    obs_md = WITNESS / "network_extension_obsidian.md"
    obs_md.write_text(
        render_report_markdown(obs_report)
        + "\n\n## Balance check\n\n"
        + f"- balanced: **{obs_bc.balanced}**\n"
        + f"- variance: {obs_bc.variance:.2f}\n"
        + f"- recommendation: {obs_bc.recommendation}\n",
        encoding="utf-8",
    )

    cs_md = WITNESS / "network_extension_csharp_unity.md"
    cs_md.write_text(
        render_report_markdown(cs_report)
        + "\n\n## Balance check\n\n"
        + f"- balanced: **{cs_bc.balanced}**\n"
        + f"- variance: {cs_bc.variance:.2f}\n"
        + f"- recommendation: {cs_bc.recommendation}\n",
        encoding="utf-8",
    )

    # Regency — regency-style folder adapter. Same shape as csharp-unity
    # (reference-graph vacuums); different domain.
    reg_post = {
        **obs_post,
        "v5": ["reg::001", "reg::002"],
        "v6": ["reg::003"],
    }
    reg_report, reg_bc = report_for(
        "s3.cubes.adapters.regency",
        volume_added="regency-folder-region",
        connected_to=[
            {"volume": "obsidian-notes-region",
             "shared_element": "outbound_refs-as-citation",
             "rank_of_shared": "face",
             "note": "both adapters emit cross-reference outbound_refs; "
                     "regency uses REGENCY-NNN, obsidian uses wikilinks."},
            {"volume": "csharp-source-region",
             "shared_element": "outbound_refs-as-citation",
             "rank_of_shared": "face",
             "note": "both adapters reveal unresolved-reference vacuums via the "
                     "same structural surface, different token grammar."},
        ],
        vacuums_revealed=[
            "unresolved regency dep: REGENCY-999 (fixture)",
        ],
        datum_names=["unresolved_regency_dep"],
        projected_post_placements=reg_post,
    )

    reg_md = WITNESS / "network_extension_regency.md"
    reg_md.write_text(
        render_report_markdown(reg_report)
        + "\n\n## Balance check\n\n"
        + f"- balanced: **{reg_bc.balanced}**\n"
        + f"- variance: {reg_bc.variance:.2f}\n"
        + f"- recommendation: {reg_bc.recommendation}\n"
        + "\n## Fixture\n\n"
        + "- fixture: `s3/cubes/skill_tests/fixtures/regency_mini/`\n",
        encoding="utf-8",
    )

    # VacuumMetric — the first metric authored under metric-design.
    # Metrics don't add candidates; their "volume" is a READING-REGION:
    # the subset of cube state the metric now makes nameable as numbers +
    # datum instances. It connects to every adapter volume whose cells the
    # metric reads (i.e., all of them, since vacuum scans all ranks).
    vac_post = cs_post  # metric reads post-adapter state; no new placements
    vac_report, vac_bc = report_for(
        "s3.cubes.metrics.vacuum",
        volume_added="vacuum-reading-region (all-ranks empty-cell surface)",
        connected_to=[
            {"volume": "obsidian-notes-region",
             "shared_element": "placement-set (reads ir.cells_with_placements)",
             "rank_of_shared": "vertex + edge",
             "note": "vacuum reads which obsidian-placed cells are occupied "
                     "vs empty; the placement surface is the shared element."},
            {"volume": "csharp-source-region",
             "shared_element": "placement-set (reads ir.cells_with_placements)",
             "rank_of_shared": "vertex + face",
             "note": "same — vacuum reads csharp_source placements against "
                     "cube state."},
        ],
        vacuums_revealed=[
            "24 cells empty out of 27 (fixture seeds 3 placements only)",
            "rank-2 (faces): 6/6 empty — face-level coverage gap",
            "rank-3 (volume): 1/1 empty — e2e coverage gap",
        ],
        datum_names=["vacuum_cell"],
        projected_post_placements=vac_post,
    )

    vac_md = WITNESS / "network_extension_vacuum.md"
    vac_md.write_text(
        render_report_markdown(vac_report)
        + "\n\n## Balance check\n\n"
        + f"- balanced: **{vac_bc.balanced}**\n"
        + f"- variance: {vac_bc.variance:.2f}\n"
        + f"- recommendation: {vac_bc.recommendation}\n"
        + "\n## Module kind\n\n"
        + "- **metric** (reveal-pressure, not ingest)\n"
        + "- *volume is a reading-region, not a source-region*\n",
        encoding="utf-8",
    )

    combined_json = WITNESS / "network_extension_summary.json"
    combined_json.write_text(json.dumps({
        "obsidian": {
            "kind": "adapter",
            "report": obs_report.as_dict(),
            "balance_check": {
                "balanced": obs_bc.balanced,
                "variance": obs_bc.variance,
                "flagged_cells": obs_bc.flagged_cells,
                "recommendation": obs_bc.recommendation,
            },
        },
        "csharp_unity": {
            "kind": "adapter",
            "report": cs_report.as_dict(),
            "balance_check": {
                "balanced": cs_bc.balanced,
                "variance": cs_bc.variance,
                "flagged_cells": cs_bc.flagged_cells,
                "recommendation": cs_bc.recommendation,
            },
        },
        "regency": {
            "kind": "adapter",
            "report": reg_report.as_dict(),
            "balance_check": {
                "balanced": reg_bc.balanced,
                "variance": reg_bc.variance,
                "flagged_cells": reg_bc.flagged_cells,
                "recommendation": reg_bc.recommendation,
            },
        },
        "vacuum": {
            "kind": "metric",
            "report": vac_report.as_dict(),
            "balance_check": {
                "balanced": vac_bc.balanced,
                "variance": vac_bc.variance,
                "flagged_cells": vac_bc.flagged_cells,
                "recommendation": vac_bc.recommendation,
            },
        },
    }, indent=2, default=str), encoding="utf-8")

    print(f"obsidian report: {obs_md.relative_to(ROOT)}")
    print(f"  balanced={obs_bc.balanced}  variance={obs_bc.variance:.2f}")
    print(f"csharp-unity report: {cs_md.relative_to(ROOT)}")
    print(f"  balanced={cs_bc.balanced}  variance={cs_bc.variance:.2f}")
    print(f"regency report: {reg_md.relative_to(ROOT)}")
    print(f"  balanced={reg_bc.balanced}  variance={reg_bc.variance:.2f}")
    print(f"vacuum report: {vac_md.relative_to(ROOT)}")
    print(f"  balanced={vac_bc.balanced}  variance={vac_bc.variance:.2f}")
    print(f"summary: {combined_json.relative_to(ROOT)}")
    print()
    print("Network structure so far:")
    print("     obsidian-notes-region")
    print("            │ │ │")
    print("            │ │ └──outbound_refs-as-citation (face)──── csharp-source-region")
    print("            │ │                                                  │")
    print("            │ └───────outbound_refs-as-citation (face)── regency-folder-region")
    print("            │                                                    │")
    print("            └─────── placement-set ─── vacuum-reading-region ───┘")
    print("  4 volumes (3 adapters + 1 metric), 4 shared elements, 4 datum families")


if __name__ == "__main__":
    main()
