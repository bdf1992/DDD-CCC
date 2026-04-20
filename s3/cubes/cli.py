"""
Coverage Cube CLI — full command surface.

State persists on disk under `.cube/` (or whatever directory `--cube-dir` names):
    .cube/sources.json        — configured source adapters
    .cube/candidates.jsonl    — SourceRecord set from ingestion
    .cube/axis_convention.json — committed axis convention
    .cube/datapoints.jsonl    — signed datapoint chain (truth source)

On every command that reads IR, the CLI materializes state from disk by:
    1. Loading candidates from candidates.jsonl
    2. Loading axis convention
    3. Replaying the datapoint chain to derive current placements

On every command that mutates, the CLI:
    1. Applies the mutation via the placement engine (decide.py)
    2. Appends a signed datapoint to datapoints.jsonl
    3. Verifies the chain remains valid

Namespaces:
    cube status                               — print state summary
    cube sources list | add <kind> <path>     — configure adapters
    cube ingest                               — run adapters, build candidates
    cube profile                              — assemble + print Profile Card
    cube axes propose                         — derive axes from candidates
    cube axes commit [--name slot=name ...]   — commit convention
    cube suggest [<source_id>]                — placement suggestions
    cube accept|reject|modify <args>          — placement decisions
    cube coverage|vacuums|frustrations|richness  — metric reads
    cube datum list|validate|register|show|packs|schema  — datum authoring
    cube datums run [--family X]              — execute registered datums against IR
    cube rag <query>                          — contextual RAG (stub)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from s3.cubes.adapters import (
    SourceRecord, SourceRef,
    FilesystemMarkdownAdapter, ObsidianVaultAdapter, GreenfieldJsonlAdapter,
    FilesystemCodeAdapter,
)
from s3.cubes.combinatorial_complex import build_cube_cc
from s3.cubes.ir import KnowledgeIR, empty_ir
from s3.cubes.profile import (
    assemble_profile_card, propose_axes, commit_convention,
    AxisConvention, validate_axis_proposal,
)
from s3.cubes.placement import (
    suggest_placements,
    PlacementDecision, DecisionKind, apply_decision,
    write_jsonl_stream,
)
from s3.cubes.placement.emit import verify_chain
from s3.cubes.metrics import (
    MetricRegistry,
    CoverageMetric, VacuumMetric, FrustrationMetric, RichnessMetric,
)
from s3.cubes.metrics.base import run_all
from s3.cubes.datums import (
    Datum, DatumFamily, DatumTier,
    DatumContext,
    DatumRegistry, ValidationError,
    load_datum_from_file, datum_to_yaml,
)
from s3.cubes.datums.packs import register_all as register_all_datum_packs


# =============================================================================
# ADAPTER REGISTRY
# =============================================================================

ADAPTER_KINDS = {
    "markdown": FilesystemMarkdownAdapter,
    "obsidian": ObsidianVaultAdapter,
    "greenfield-jsonl": GreenfieldJsonlAdapter,
    "code": FilesystemCodeAdapter,
}


def _make_adapter(kind: str, path: str):
    cls = ADAPTER_KINDS.get(kind)
    if cls is None:
        raise ValueError(f"unknown adapter kind: {kind}. Known: {sorted(ADAPTER_KINDS)}")
    if kind == "greenfield-jsonl":
        return cls(path)
    return cls(path)


# =============================================================================
# CUBE STATE — persistence on disk
# =============================================================================

class CubeState:
    """On-disk cube state at <cube_dir>/ (default .cube/)."""

    def __init__(self, cube_dir: Path):
        self.root = Path(cube_dir)
        self.sources_path = self.root / "sources.json"
        self.candidates_path = self.root / "candidates.jsonl"
        self.convention_path = self.root / "axis_convention.json"
        self.datapoints_path = self.root / "datapoints.jsonl"

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.root.exists()

    # --- sources ---

    def load_sources(self) -> list[dict]:
        if not self.sources_path.exists():
            return []
        return json.loads(self.sources_path.read_text(encoding="utf-8"))

    def save_sources(self, sources: list[dict]) -> None:
        self.initialize()
        self.sources_path.write_text(json.dumps(sources, indent=2), encoding="utf-8")

    # --- candidates ---

    def load_candidates(self) -> list[SourceRecord]:
        if not self.candidates_path.exists():
            return []
        out: list[SourceRecord] = []
        with self.candidates_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                out.append(SourceRecord(**d))
        return out

    def save_candidates(self, records: list[SourceRecord]) -> None:
        self.initialize()
        with self.candidates_path.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(asdict(r)) + "\n")

    # --- axis convention ---

    def load_convention(self) -> Optional[AxisConvention]:
        if not self.convention_path.exists():
            return None
        d = json.loads(self.convention_path.read_text(encoding="utf-8"))
        return AxisConvention(
            slot_to_name={int(k): v for k, v in d.get("slot_to_name", {}).items()},
            slot_to_signal={int(k): v for k, v in d.get("slot_to_signal", {}).items()},
            confirmed_at=d.get("confirmed_at", ""),
            confirmed_by=d.get("confirmed_by", ""),
            evidence={int(k): v for k, v in d.get("evidence", {}).items()},
        )

    def save_convention(self, convention: AxisConvention) -> None:
        self.initialize()
        self.convention_path.write_text(
            json.dumps(convention.to_dict(), indent=2), encoding="utf-8"
        )

    # --- datapoint chain ---

    def load_datapoints(self) -> list[dict]:
        if not self.datapoints_path.exists():
            return []
        out: list[dict] = []
        with self.datapoints_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out

    def append_datapoint(self, dp: dict) -> None:
        self.initialize()
        with self.datapoints_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dp) + "\n")

    # --- materialize IR ---

    def materialize_ir(self) -> KnowledgeIR:
        """Replay the on-disk state into a fresh KnowledgeIR."""
        cube = build_cube_cc()
        ir = empty_ir(cube=cube)
        ir.candidates = self.load_candidates()

        conv = self.load_convention()
        if conv is not None:
            ir.axis_convention = dict(conv.slot_to_name)

        # Replay datapoints to derive placements
        for dp in self.load_datapoints():
            ir.provenance.append(dp)
            if dp.get("kind") != "cube.placement_decision":
                continue
            decision = dp.get("decision")
            sid = dp.get("source_id")
            cell = dp.get("cell_label")
            old_cell = dp.get("old_cell")
            if decision == "accept" and cell and sid:
                ir.place(cell, sid)
            elif decision == "modify" and cell and sid:
                if old_cell:
                    ir.unplace(old_cell, sid)
                ir.place(cell, sid)
            elif decision == "unplace" and cell and sid:
                ir.unplace(cell, sid)
            # reject: no state change

        return ir


def _get_state(args) -> CubeState:
    return CubeState(Path(args.cube_dir))


# =============================================================================
# SHARED METRIC REGISTRY
# =============================================================================

def _build_metric_registry() -> MetricRegistry:
    reg = MetricRegistry()
    reg.register(CoverageMetric())
    reg.register(VacuumMetric())
    reg.register(FrustrationMetric())
    reg.register(RichnessMetric())
    return reg


def _build_datum_registry() -> DatumRegistry:
    reg = DatumRegistry()
    register_all_datum_packs(reg)
    return reg


# =============================================================================
# COMMANDS
# =============================================================================

def cmd_status(args) -> int:
    state = _get_state(args)
    if not state.exists():
        print(f"No cube state at {state.root}. Run `cube sources add` to initialize.")
        return 0
    sources = state.load_sources()
    ir = state.materialize_ir()
    conv = state.load_convention()

    if args.json:
        print(json.dumps({
            "cube_dir": str(state.root),
            "sources": sources,
            "candidates": len(ir.candidates),
            "placements": ir.placement_count(),
            "placed_cells": len(ir.cells_with_placements()),
            "datapoints": len(ir.provenance),
            "axis_convention": ir.axis_convention,
            "fingerprint": ir.fingerprint(),
        }, indent=2))
        return 0

    print(f"Cube state at: {state.root}")
    print(f"  sources:       {len(sources)}")
    for s in sources:
        print(f"    {s['kind']:<18} {s['path']}")
    print(f"  candidates:    {len(ir.candidates)}")
    print(f"  placements:    {ir.placement_count()} across {len(ir.cells_with_placements())} cells")
    print(f"  datapoints:    {len(ir.provenance)}")
    print(f"  axes:          {ir.axis_convention if ir.axis_convention else '(not committed)'}")
    print(f"  fingerprint:   {ir.fingerprint()}")
    return 0


# --- sources ---

def cmd_sources_list(args) -> int:
    state = _get_state(args)
    sources = state.load_sources()
    if not sources:
        print("(no sources configured)")
        return 0
    for i, s in enumerate(sources):
        print(f"  [{i}] {s['kind']:<18} {s['path']}")
    return 0


def cmd_sources_add(args) -> int:
    if args.kind not in ADAPTER_KINDS:
        print(f"FAIL — unknown adapter kind: {args.kind}. Known: {sorted(ADAPTER_KINDS)}")
        return 2
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"FAIL — path does not exist: {path}")
        return 2
    state = _get_state(args)
    state.initialize()
    sources = state.load_sources()
    # de-dup by (kind, path)
    for s in sources:
        if s["kind"] == args.kind and Path(s["path"]).resolve() == path:
            print(f"already configured: {args.kind} {path}")
            return 0
    sources.append({"kind": args.kind, "path": str(path)})
    state.save_sources(sources)
    print(f"added: {args.kind} {path}")
    return 0


# --- ingest ---

def cmd_ingest(args) -> int:
    state = _get_state(args)
    sources = state.load_sources()
    if not sources:
        print("FAIL — no sources configured. Run `cube sources add <kind> <path>` first.")
        return 2

    all_records: list[SourceRecord] = []
    for s in sources:
        try:
            adapter = _make_adapter(s["kind"], s["path"])
        except ValueError as e:
            print(f"FAIL — {e}")
            return 2
        refs = adapter.discover()
        for r in refs:
            rec = adapter.read(r)
            all_records.append(rec)
        print(f"  {s['kind']:<18} discovered {len(refs):>4}  path={s['path']}")

    # Deduplicate by source_id (last-write-wins)
    by_id: dict[str, SourceRecord] = {}
    for r in all_records:
        by_id[r.source_id] = r
    final = list(by_id.values())
    state.save_candidates(final)
    print(f"ingested {len(final)} candidates -> {state.candidates_path}")
    return 0


# --- profile ---

def cmd_profile(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    if not ir.candidates:
        print("FAIL — no candidates. Run `cube ingest` first.")
        return 2
    card = assemble_profile_card(ir.candidates)
    if args.json:
        print(json.dumps(asdict(card), indent=2, default=str))
        return 0
    print("Profile Card")
    print(f"  name:              {card.name or '(not inferable)'}")
    print(f"  primary_purpose:   {card.primary_purpose or '(not inferable)'}")
    print(f"  domain:            {card.domain or '(not inferable)'}")
    print(f"  dominant_language: {card.dominant_language or '(not inferable)'}")
    print(f"  stakeholders:      {card.stakeholders or '(none)'}")
    print(f"  maturity:          {card.maturity}")
    print(f"  evidence sources:  {card.evidence_count()}")
    return 0


# --- axes ---

def cmd_axes_propose(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    if not ir.candidates:
        print("FAIL — no candidates. Run `cube ingest` first.")
        return 2
    proposal = propose_axes(ir.candidates)
    errs = validate_axis_proposal(proposal)

    if args.json:
        print(json.dumps({
            "axes": [
                {"slot": ax.slot, "name": ax.name, "signal": ax.source_signal,
                 "entropy": ax.entropy, "bins": ax.bins}
                for ax in proposal.axes
            ],
            "rejected_signals": proposal.rejected_signals,
            "invariant_errors": errs,
        }, indent=2))
        return 0

    print(f"Proposed {len(proposal.axes)} axes:")
    for ax in proposal.axes:
        top = [b["label"] for b in ax.bins[:3]]
        print(f"  slot {ax.slot}: name={ax.name!r} signal={ax.source_signal!r} "
              f"entropy={ax.entropy:.3f} top_bins={top}")
    if proposal.rejected_signals:
        print(f"Rejected signals ({len(proposal.rejected_signals)}):")
        for r in proposal.rejected_signals:
            print(f"  {r['source_signal']}: {r['reason']} "
                  f"(bins={r['distinct_bins']}, entropy={r['entropy']})")
    print(f"Universal invariant check: {'PASS' if not errs else 'FAIL'}")
    for e in errs:
        print(f"  - {e}")
    return 0 if not errs else 2


def cmd_axes_commit(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    if not ir.candidates:
        print("FAIL — no candidates. Run `cube ingest` first.")
        return 2
    proposal = propose_axes(ir.candidates)
    confirmations: dict[int, str] = {}
    for assignment in (args.name or []):
        if "=" not in assignment:
            print(f"FAIL — bad --name assignment: {assignment} (expected slot=name)")
            return 2
        slot_str, name = assignment.split("=", 1)
        try:
            confirmations[int(slot_str)] = name.strip()
        except ValueError:
            print(f"FAIL — slot not an integer: {slot_str}")
            return 2
    try:
        convention = commit_convention(
            proposal, confirmations=confirmations or None, confirmed_by="cli"
        )
    except ValueError as e:
        print(f"FAIL — {e}")
        return 2
    state.save_convention(convention)
    print("COMMITTED axis convention:")
    for slot in sorted(convention.slot_to_name):
        print(f"  slot {slot}: {convention.slot_to_name[slot]!r} "
              f"<= signal={convention.slot_to_signal[slot]!r}")
    return 0


# --- suggest ---

def cmd_suggest(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    if not ir.candidates:
        print("FAIL — no candidates. Run `cube ingest` first.")
        return 2

    by_id = ir.candidates_by_id()
    if args.source_id:
        if args.source_id not in by_id:
            print(f"FAIL — unknown source_id: {args.source_id}")
            return 2
        targets = [by_id[args.source_id]]
    else:
        # Top N unplaced candidates
        placed_ids: set[str] = set()
        for cell, ids in ir.placements.items():
            placed_ids.update(ids)
        unplaced = [c for c in ir.candidates if c.source_id not in placed_ids]
        targets = unplaced[:args.top_candidates]

    for rec in targets:
        suggestion = suggest_placements(rec, ir, limit=args.limit)
        if args.json:
            print(json.dumps({
                "source_id": rec.source_id,
                "title": rec.title,
                "candidates": [
                    {"cell_label": c.cell_label, "rank": c.cell_rank,
                     "score": c.score, "reasons": c.reasons,
                     "predictive": c.predictive}
                    for c in suggestion.candidates
                ],
            }))
            continue
        print(f"[{rec.source_id}] {rec.title or rec.uri}")
        for c in suggestion.candidates:
            print(f"    {c.cell_label:<10} rank={c.cell_rank}  score={c.score:.3f}  "
                  f"reasons={c.reasons}")
    return 0


# --- placement decisions ---

def _apply_cli_decision(state: CubeState, decision: PlacementDecision) -> int:
    ir = state.materialize_ir()
    try:
        _, signed = apply_decision(ir, decision)
    except ValueError as e:
        print(f"FAIL — {e}")
        return 2
    state.append_datapoint(signed.to_dict())
    print(f"OK — {decision.kind.value} {decision.source_id} -> {decision.cell_label}")
    print(f"      signed event: {signed.event_id}")
    return 0


def cmd_accept(args) -> int:
    state = _get_state(args)
    d = PlacementDecision(
        kind=DecisionKind.ACCEPT, source_id=args.source_id,
        cell_label=args.cell, reasoning=args.reason or "", actor=args.actor or "cli",
    )
    return _apply_cli_decision(state, d)


def cmd_reject(args) -> int:
    state = _get_state(args)
    d = PlacementDecision(
        kind=DecisionKind.REJECT, source_id=args.source_id,
        cell_label=args.cell, reasoning=args.reason or "", actor=args.actor or "cli",
    )
    return _apply_cli_decision(state, d)


def cmd_modify(args) -> int:
    state = _get_state(args)
    d = PlacementDecision(
        kind=DecisionKind.MODIFY, source_id=args.source_id,
        cell_label=args.new_cell, old_cell=args.old_cell,
        reasoning=args.reason or "", actor=args.actor or "cli",
    )
    return _apply_cli_decision(state, d)


# --- metrics ---

def _run_single_metric(args, metric_name: str) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    reg = _build_metric_registry()
    plugin = reg.get(metric_name)
    if plugin is None:
        print(f"FAIL — unknown metric: {metric_name}")
        return 2
    result = plugin.measure(ir)
    if args.json:
        print(json.dumps({
            "name": result.name,
            "summary": result.summary,
            "scalars": result.scalars,
        }, indent=2))
        return 0
    print(result.summary)
    for k, v in sorted(result.scalars.items()):
        print(f"  {k:<30} {v}")
    return 0


def cmd_coverage(args) -> int:
    return _run_single_metric(args, "coverage")


def cmd_vacuums(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    reg = _build_metric_registry()
    result = reg.get("vacuum").measure(ir)
    if args.json:
        print(json.dumps({
            "summary": result.summary,
            "scalars": result.scalars,
            "vacuum_cells": [k for k, v in result.cell_readings.items()
                             if v.get("is_vacuum")],
        }, indent=2))
        return 0
    print(result.summary)
    cells = [k for k, v in result.cell_readings.items() if v.get("is_vacuum")]
    for c in sorted(cells):
        print(f"  {c}")
    return 0


def cmd_frustrations(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    reg = _build_metric_registry()
    result = reg.get("frustration").measure(ir)
    if args.json:
        print(json.dumps({
            "summary": result.summary,
            "scalars": result.scalars,
            "frustrated_cells": list(result.cell_readings.keys()),
        }, indent=2))
        return 0
    print(result.summary)
    for cell_label, reading in sorted(result.cell_readings.items()):
        print(f"  {cell_label:<10} {reading}")
    return 0


def cmd_richness(args) -> int:
    return _run_single_metric(args, "richness")


# --- datums run ---

def cmd_datums_run(args) -> int:
    state = _get_state(args)
    ir = state.materialize_ir()
    if not ir.candidates:
        print("FAIL — no candidates. Run `cube ingest` first.")
        return 2
    reg = _build_datum_registry()
    family = DatumFamily(args.family) if args.family else None
    datums = reg.list(family=family)

    ctx = DatumContext(candidates=ir.candidates, placements=dict(ir.placements), cube=ir.cube)
    all_instances = []
    for d in datums:
        instances = d.execute(ctx)
        all_instances.extend(instances)
        if not args.json:
            print(f"{d.qualified_name:<50} -> {len(instances)} instance(s)")
            for inst in instances:
                print(f"  [{inst.severity:>6}] {inst.claim}")

    if args.json:
        print(json.dumps([{
            "datum": inst.datum_qualified_name,
            "severity": inst.severity,
            "claim": inst.claim,
            "evidence": inst.evidence,
            "recommended_action": inst.recommended_action,
            "cell_refs": inst.cell_refs,
            "source_refs": inst.source_refs,
        } for inst in all_instances], indent=2))
    return 0


# --- datum subcommand ---

_DATUM_SHARED_REGISTRY: Optional[DatumRegistry] = None


def _get_shared_datum_registry() -> DatumRegistry:
    global _DATUM_SHARED_REGISTRY
    if _DATUM_SHARED_REGISTRY is None:
        _DATUM_SHARED_REGISTRY = _build_datum_registry()
    return _DATUM_SHARED_REGISTRY


def cmd_datum_list(args) -> int:
    reg = _get_shared_datum_registry()
    family = DatumFamily(args.family) if args.family else None
    tier = DatumTier(args.tier) if args.tier else None
    datums = reg.list(family=family, tier=tier)
    if not datums:
        print("(no datums registered)")
        return 0
    print(f"{'qualified_name':<50} {'tier':<12} {'description'}")
    print("-" * 120)
    for d in datums:
        print(f"{d.qualified_name:<50} {d.tier.value:<12} {d.description}")
    return 0


def cmd_datum_validate(args) -> int:
    try:
        d = load_datum_from_file(args.path)
    except ValidationError as e:
        print(f"FAIL — {args.path} is not a valid datum:")
        for err in e.errors:
            print(f"  - {err}")
        return 2
    print(f"OK — {d.qualified_name} is a valid datum")
    return 0


def cmd_datum_register(args) -> int:
    reg = _get_shared_datum_registry()
    try:
        d = load_datum_from_file(args.path)
    except ValidationError as e:
        print(f"REFUSED — {args.path}:")
        for err in e.errors:
            print(f"  - {err}")
        print("\nA datum cannot register without: semantic meaning, syntactic shape,")
        print("inputs, evidence requirements, positive+negative examples, failure mode.")
        return 2
    try:
        reg.register(d)
    except ValueError as e:
        print(f"REFUSED — {e}")
        return 2
    print(f"REGISTERED — {d.qualified_name}")
    return 0


def cmd_datum_show(args) -> int:
    reg = _get_shared_datum_registry()
    d = reg.get(args.name)
    if d is None:
        print(f"no datum named '{args.name}'")
        return 2
    print(datum_to_yaml(d))
    return 0


def cmd_datum_packs(args) -> int:
    reg = _get_shared_datum_registry()
    by_family: dict[str, list[Datum]] = {}
    for d in reg.list():
        by_family.setdefault(d.family.value, []).append(d)
    print("Registered datum families + member datums:")
    for family in sorted(by_family):
        ds = by_family[family]
        print(f"  {family}  ({len(ds)} datums)")
        for d in sorted(ds, key=lambda x: x.name):
            print(f"    {d.tier.value:<12} {d.qualified_name}")
    return 0


def cmd_datum_schema(args) -> int:
    import yaml
    template = {
        "name": "my_new_datum",
        "family": "staleness",
        "tier": "primitive",
        "description": "What this datum claims, in one line.",
        "inputs": {
            "storage_signals": ["file_modified_at"],
            "interaction_signals": [],
            "cube_signals": ["cell_rank"],
            "text_signals": ["outbound_refs"],
        },
        "semantic_check": {"claim": "...", "must_have": ["evidence_kind_1"]},
        "syntactic_check": {"required_fields": ["source_id"]},
        "output": {"severity": "medium", "claim": "Template with {source_id}.",
                   "evidence": {}, "recommended_action": "..."},
        "examples": {"positive": {"case": "match"}, "negative": {"case": "near-miss"}},
        "failure_mode": "What goes wrong if overfires or underfires.",
    }
    print("# Canonical Coverage Cube datum YAML contract (template)")
    print(yaml.safe_dump(template, sort_keys=False, default_flow_style=False))
    return 0


# --- rag stub ---

def cmd_rag(args) -> int:
    print(f"contextual RAG over query: {args.query!r}")
    if args.anchor:
        print(f"  anchor cell: {args.anchor}")
    print("(stub — contextual retrieval to be delivered by the vector-store extension.)")
    return 0


# =============================================================================
# PARSER
# =============================================================================

def cmd_bootstrap(args) -> int:
    """Run the adapter-design skill protocol against a foreign repo.

    Step 0 — Read the target repo (walk, extensions, dotfiles).
    Step 1 — Read cube context (current placement state).
    Step 2 — Inventory source systems; propose candidate adapters.
    Step 3 — Audit services library.
    (Steps 4-12 require human/LLM follow-through on the adapter-design skill.)

    --dry-run stops at the inventory + proposal; omitting it prints the same
    output plus a reminder to invoke the `adapter-design` skill in an LLM
    session pointed at this repo. Bootstrap does NOT itself author modules
    (Authorship is a contextual LLM move, not a shell operation.)
    """
    from pathlib import Path as _P
    from collections import Counter
    target = _P(args.target).resolve()
    if not target.exists() or not target.is_dir():
        print(f"ERROR: target not a directory: {target}")
        return 2

    print(f"=== adapter-design bootstrap ===")
    print(f"target: {target}")
    print()

    # Step 0 — walk
    ext_counts: Counter = Counter()
    dir_markers: list[str] = []
    sample_count = 0
    for p in target.rglob("*"):
        if p.is_file():
            ext_counts[p.suffix.lower()] += 1
            sample_count += 1
            if sample_count > 20000:
                break
    for marker in (".obsidian", ".git", "pyproject.toml", "package.json",
                    "Cargo.toml", "go.mod", "Assets", "regencies",
                    ".claude/skills"):
        if (target / marker).exists():
            dir_markers.append(marker)

    print("Step 0 — repo read:")
    print(f"  files scanned: {sample_count}")
    print(f"  top 8 extensions: {ext_counts.most_common(8)}")
    print(f"  dir markers: {dir_markers}")
    print()

    # Step 1 — cube context
    try:
        state = CubeState.load(args.cube_dir)
        ir = state.build_ir()
        from s3.cubes.skill_support import read_cube_context
        ctx = read_cube_context(ir)
        print("Step 1 — cube context:")
        print(f"  placed cells: {ctx.n_placed_cells}")
        print(f"  vacuum cells: {ctx.n_vacuum_cells}")
        print(f"  placement count: {ctx.placement_count}")
        print(f"  recent provenance events: {ctx.recent_provenance_count}")
    except Exception as e:
        print(f"Step 1 — cube context: (no existing cube at {args.cube_dir}; "
              f"fresh bootstrap, {type(e).__name__})")
    print()

    # Step 2 — propose adapter targets by dir marker / extension signature
    proposals: list[str] = []
    if ".obsidian" in dir_markers:
        proposals.append("obsidian (existing reference; wire to this vault)")
    if "Assets" in dir_markers:
        proposals.append("csharp-unity (if Assets/Scripts/ has .cs files; "
                         "existing reference)")
    if "regencies" in dir_markers:
        proposals.append("regency (existing reference; wire to regencies/ dir)")
    if ext_counts.get(".md", 0) >= 10 and "obsidian" not in [p.split()[0] for p in proposals]:
        proposals.append("markdown (existing ungated adapter; may need "
                         "proofs retrofitted)")
    if ext_counts.get(".py", 0) >= 10:
        proposals.append("python-code (NOT yet in library; adapter-design "
                         "skill would author on demand)")
    if not proposals:
        proposals.append("(no existing-reference match; adapter-design skill "
                         "run needed to inventory manually)")

    print("Step 2 — proposed adapters:")
    for p in proposals:
        print(f"  - {p}")
    print()

    # Step 3 — services library
    from s3.cubes.adapters.services import audit_library
    aud = audit_library()
    print(f"Step 3 — services library: "
          f"{aud['n_green']}/{aud['n_services']} green")
    for r in aud["results"]:
        print(f"  - {r['service']}: {r['summary']}")

    print()
    if args.dry_run:
        print("--dry-run: stopping before authorship. Steps 4-12 (compose / "
              "author / fixture / test / register / flip / report) require "
              "an LLM session invoking the adapter-design skill.")
    else:
        print("NEXT: invoke the adapter-design skill in an LLM session pointed "
              "at this repo. The skill's 12-step protocol takes the output "
              "above and authors modules on demand. See "
              ".claude/skills/adapter-design/SKILL.md for the protocol.")
    return 0


def cmd_proofs(args) -> int:
    """Run the four-proof harness across every manifest-declared module."""
    from s3.cubes.run_proofs import main as _run_main
    return _run_main()


def cmd_skills(args) -> int:
    """List authorship + workflow skills declared in _manifest.yaml."""
    from s3.cubes.manifest import load_manifest
    # Manifest lives alongside this package: search from package install up to repo root.
    here = Path(__file__).resolve()
    for parent in [here.parents[2], here.parents[3], Path.cwd()]:
        candidate = parent / ".claude" / "skills" / "_manifest.yaml"
        if candidate.exists():
            manifest_path = candidate
            break
    else:
        print("ERROR: _manifest.yaml not found; expected .claude/skills/_manifest.yaml")
        return 2
    m = load_manifest(manifest_path)
    print(f"manifest: {manifest_path}")
    print(f"instance: {m.instance}")
    print(f"fingerprint: {m.fingerprint()[:22]}...")
    print(f"\nworkflow skills ({len(m.workflow_skills)}):")
    for s in m.workflow_skills:
        print(f"  - {s}")
    print(f"\nauthorship skills ({len(m.authorship_skills)}):")
    for s in m.authorship_skills:
        print(f"  - {s}")
    print(f"\nexports ({len(m.modules)}):")
    for kind in ("adapters", "metrics", "datum_packs", "sweeps",
                  "observations", "transducers", "dashboard_panels"):
        entries = m.by_kind(kind)
        if not entries:
            continue
        print(f"  {kind}:")
        for e in entries:
            print(f"    - {e.name} [{e.proof_status}]")
    return 0


def cmd_network(args) -> int:
    """Render the current network-of-volumes report."""
    import json as _json
    here = Path(__file__).resolve()
    root = here.parents[2]
    summary = root / ".cube" / "reports" / "network" / "network_extension_summary.json"
    if not summary.exists():
        from s3.cubes.run_network import main as _run_network
        _run_network()
        if not summary.exists():
            print(f"ERROR: network report generation failed; expected {summary}.")
            return 2
    data = _json.loads(summary.read_text(encoding="utf-8"))
    print(f"=== Network of volumes ===")
    print(f"Source: {summary.relative_to(root)}")
    print()
    for name, entry in data.items():
        kind = entry.get("kind", "?")
        report = entry.get("report", {})
        bc = entry.get("balance_check", {})
        mark = "OK" if bc.get("balanced") else "IMBALANCED"
        print(f"[{mark}] {name} ({kind})")
        print(f"       volume: {report.get('volume_added', '?')}")
        for c in report.get("connected_to", []):
            print(f"       ~~ connected to {c.get('volume', '?')} via "
                  f"{c.get('shared_element', '?')}")
        datums = report.get("datum_names", [])
        print(f"       datums: {datums}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cube", description="Coverage Cube CLI")
    p.add_argument("--cube-dir", default=".cube",
                   help="state directory (default: .cube)")
    p.add_argument("--json", action="store_true",
                   help="JSON output where supported")
    sub = p.add_subparsers(dest="namespace", required=True)

    # status
    s = sub.add_parser("status", help="show current cube state")
    s.set_defaults(func=cmd_status)

    # sources
    src = sub.add_parser("sources", help="configure source adapters")
    src_sub = src.add_subparsers(dest="action", required=True)
    sl = src_sub.add_parser("list"); sl.set_defaults(func=cmd_sources_list)
    sa = src_sub.add_parser("add")
    sa.add_argument("kind", choices=sorted(ADAPTER_KINDS))
    sa.add_argument("path")
    sa.set_defaults(func=cmd_sources_add)

    # ingest
    ing = sub.add_parser("ingest", help="run adapters, build candidate pool")
    ing.set_defaults(func=cmd_ingest)

    # profile
    prof = sub.add_parser("profile", help="assemble + print Profile Card")
    prof.set_defaults(func=cmd_profile)

    # axes
    ax = sub.add_parser("axes", help="propose / commit axis convention")
    ax_sub = ax.add_subparsers(dest="action", required=True)
    axp = ax_sub.add_parser("propose"); axp.set_defaults(func=cmd_axes_propose)
    axc = ax_sub.add_parser("commit")
    axc.add_argument("--name", action="append", default=[],
                     help="slot=name assignment (repeatable); overrides proposer default")
    axc.set_defaults(func=cmd_axes_commit)

    # suggest
    sug = sub.add_parser("suggest", help="ranked placement suggestions")
    sug.add_argument("source_id", nargs="?", default=None)
    sug.add_argument("--limit", type=int, default=3)
    sug.add_argument("--top-candidates", type=int, default=3,
                     help="if no source_id given, suggest for top-N unplaced candidates")
    sug.set_defaults(func=cmd_suggest)

    # accept / reject / modify
    for name, fn in (("accept", cmd_accept), ("reject", cmd_reject)):
        c = sub.add_parser(name, help=f"{name} a placement")
        c.add_argument("source_id")
        c.add_argument("cell")
        c.add_argument("--reason", default="")
        c.add_argument("--actor", default="cli")
        c.set_defaults(func=fn)
    mod = sub.add_parser("modify", help="move a placement from old_cell to new_cell")
    mod.add_argument("source_id")
    mod.add_argument("old_cell")
    mod.add_argument("new_cell")
    mod.add_argument("--reason", default="")
    mod.add_argument("--actor", default="cli")
    mod.set_defaults(func=cmd_modify)

    # metrics
    sub.add_parser("coverage", help="cell coverage per rank").set_defaults(func=cmd_coverage)
    sub.add_parser("vacuums", help="empty cells").set_defaults(func=cmd_vacuums)
    sub.add_parser("frustrations", help="H^0 disagreement edges/faces").set_defaults(func=cmd_frustrations)
    sub.add_parser("richness", help="rank-weighted density").set_defaults(func=cmd_richness)

    # datums run
    dr = sub.add_parser("datums", help="run registered datum packs against IR")
    dr_sub = dr.add_subparsers(dest="action", required=True)
    drr = dr_sub.add_parser("run")
    drr.add_argument("--family", default=None,
                     choices=sorted(f.value for f in DatumFamily))
    drr.set_defaults(func=cmd_datums_run)

    # datum (authoring subcommands)
    datum = sub.add_parser("datum", help="datum authoring + registry commands")
    datum_sub = datum.add_subparsers(dest="action", required=True)
    ls = datum_sub.add_parser("list")
    ls.add_argument("--family", default=None)
    ls.add_argument("--tier", default=None)
    ls.set_defaults(func=cmd_datum_list)
    val = datum_sub.add_parser("validate"); val.add_argument("path"); val.set_defaults(func=cmd_datum_validate)
    reg = datum_sub.add_parser("register"); reg.add_argument("path"); reg.set_defaults(func=cmd_datum_register)
    show = datum_sub.add_parser("show"); show.add_argument("name"); show.set_defaults(func=cmd_datum_show)
    datum_sub.add_parser("packs").set_defaults(func=cmd_datum_packs)
    datum_sub.add_parser("schema").set_defaults(func=cmd_datum_schema)

    # rag
    rag = sub.add_parser("rag", help="contextual RAG query (stub)")
    rag.add_argument("query")
    rag.add_argument("--anchor", default=None)
    rag.set_defaults(func=cmd_rag)

    # Audit + authorship entry points ----------------------------------------

    boot = sub.add_parser("bootstrap",
                           help="run adapter-design protocol against a foreign repo")
    boot.add_argument("target", help="path to the foreign repo to inspect")
    boot.add_argument("--dry-run", action="store_true",
                       help="inventory + propose only; do NOT author modules")
    boot.set_defaults(func=cmd_bootstrap)

    prf = sub.add_parser("proofs",
                          help="run the four-proof harness against manifest modules")
    prf.set_defaults(func=cmd_proofs)

    sk = sub.add_parser("skills",
                         help="list authorship + workflow skills from _manifest.yaml")
    sk.set_defaults(func=cmd_skills)

    net = sub.add_parser("network",
                          help="render the current network-of-volumes report")
    net.set_defaults(func=cmd_network)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
