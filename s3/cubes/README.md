# Coverage Cube

A pluggable dynamical measurement substrate over a combinatorial complex. Ingests heterogeneous knowledge (code, prose, Markdown, Obsidian, Greenfield JSONL, SQL schemas, C# sources, Regency folders, ...), places candidates onto semantic cells, emits typed cited datums, runs a four-proof authorship discipline, and ships a signed hash-chained datapoint stream.

**Version**: 0.1.0 — first public release. Ships substrate + contextual-skill pattern + authorship library. See `RELEASE_NOTES.md` for what's in / deferred.

---

## Quickstart

```bash
# 1. Clone
git clone <this-repo-url> coverage-cube
cd coverage-cube

# 2. Install (editable recommended while the surface is still stabilizing)
pip install -e .

# 3. Confirm install
cube --help
cube skills
cube proofs         # runs the four-proof harness against every green module
```

Expected output of `cube proofs` on a fresh install:

```
  [OK] adapters/obsidian:      4/4 proofs
  [OK] adapters/csharp-unity:  4/4 proofs
  [OK] adapters/regency:       4/4 proofs
  [OK] metrics/vacuum:         4/4 proofs
  totals: 4 green · 0 fail · 6 ungated
  acceptance met: ≥1 adapter fully proven, no failing proofs.
```

If all four lines are `[OK]`, the install is correct.

---

## The full cycle (what to test end-to-end)

The full cycle exercises the substrate + skills + routines + datum-chain in one pass against a foreign repo. The same sequence applies to any target.

```bash
# Step A — inventory the target repo (no authorship yet)
cube bootstrap /path/to/target-repo --dry-run

#   Reports: files scanned, top extensions, dir markers, proposed adapters,
#   services library audit (4/4 green). Stops at Step 3 of adapter-design.

# Step B — audit the current network of volumes
cube network

#   Renders the 4 existing green volumes + their connections.
#   Expected: 3 adapter volumes sharing one face; 1 metric volume reading all three.

# Step C — run the proof harness + read the witness artifacts
cube proofs
ls .cube/reports/

#   Expected witness: proofs.md (rendered four-proof report),
#                      proofs_summary.json (JSON),
#                      network/network_extension_*.md (per-volume reports).

# Step D — author a new adapter for your target (requires LLM session)
#   Invoke the `adapter-design` skill in a Claude Code session pointed at the
#   target repo. The skill follows its 12-step generative protocol:
#     1. read the target repo
#     2. read cube context
#     3. inventory source systems
#     4. audit services
#     5. compose or extend services
#     6. author the adapter module
#     7. carve a fixture
#     8. write the test module
#     9. run balance check
#    10. register in manifest
#    11. flip proof_status: green
#    12. emit network-extension report
#
#   At the end, `cube proofs` shows one more green row and `cube network`
#   shows the new volume connected to the existing network.

# Step E — re-run the full proof cycle
cube proofs
cube network
```

Successful run = one additional green module + one additional volume in the network.

---

## CLI reference

### Workflow commands (operate the substrate)

| Command | Role |
|---|---|
| `cube status` | Show current cube state in `.cube/` |
| `cube sources list` / `sources add <kind> <path>` | Configure source adapters |
| `cube ingest` | Run adapters, build candidate pool |
| `cube profile` | Assemble + print Profile Card |
| `cube axes propose` / `axes commit <...>` | Propose + commit axis convention |
| `cube suggest [candidate]` | Top-N ranked placement suggestions |
| `cube accept / reject / modify` | Record placement decisions (anchor + correction points) |
| `cube coverage / vacuums / frustrations / richness` | Metric plugin readings |
| `cube datums run` / `datum list / validate / register / show` | Datum pack operations |

### Audit + authorship commands

| Command | Role |
|---|---|
| `cube skills` | List authorship + workflow skills declared in `.claude/skills/_manifest.yaml` |
| `cube proofs` | Run the four-proof harness against every manifest-declared module |
| `cube network` | Render the current network-of-volumes report |
| `cube bootstrap <repo> [--dry-run]` | Run Steps 0–3 of the adapter-design skill against a foreign repo |

---

## The authorship surface

Coverage Cube is **not one skill** — it is a library of module-authoring skills composed by a declarative manifest. Each skill shares the **four-proof discipline** (pressure / data-derivable datum / corrective hook / dual test) and the **contextual-skill pattern** (two obligations: *create-datum* + *semantic-balance*; four-piece protocol: *intent-as-pressure* / *context-before-propose* / *datum-first-network-extension-output* / *semantic-balance check*).

**Workflow skills**:
- `cube` — ingest / measure / audit (this is where you operate)

**Authorship skills** (each authors one module kind):
- `adapter-design` — author a new `SourceAdapter` by reading a target repo (reference adapters: obsidian, csharp-unity, regency)
- `metric-design` — author a new `MetricPlugin` by reading cube state (reference metric: vacuum)
- `datum-design` — define a new actionable signal derived from data (reference pack: staleness)
- `observation-design` — chunked-ETL observer for Progressive Discovery
- `dashboard-design` — reveal-to-human panels
- `sweep-design` — orbit-integrated sweeps (group-action invariants + anisotropy)
- `transducer-design` — Knowledge Shape transducers (ships as a STUB; full authorship surface planned for a later release)

Skills live at `.claude/skills/<skill-name>/SKILL.md` and are discoverable by Claude Code + any compatible agent runtime.

---

## The four-proof discipline

Every module-skill ships **four proofs** or it does not ship:

1. **Pressure claim** — loggable against specific cells / candidates / datums
2. **Data-derivable datum** — computed from inputs, never hand-authored prose (every instance's `evidence` field cites the data it was derived from)
3. **Corrective pattern hook** — user rejections measurably shift subsequent output (before ≠ after)
4. **Dual test** — code TDD passes AND a skill-vs-code agreement test verifies the authored module integrates

Enforced at `cube proofs` (backed by `s3.cubes.run_proofs`).

---

## Current manifest state (0.1.0 shipment)

```
services library:   4/4 green
  wikilink_extractor, csharp_usings, csharp_namespace, regency_refs

adapters:           3 green / 4 ungated
  obsidian (Obsidian-style vault), csharp-unity (Unity C# tree), regency (regency-style folder)
  ungated: markdown, greenfield-jsonl, filesystem-code (reference patterns)

metrics:            1 green / 3 ungated
  vacuum (substrate reading-region)
  ungated: coverage, frustration, richness (reference patterns)

datum_packs:        0 green / 1 ungated
  staleness (reference pack; ungated here, fully authored in source)

authorship skills:  7 shipped
  adapter-design, metric-design, datum-design, observation-design,
  dashboard-design, sweep-design, transducer-design (stub)
```

Ungated modules remain on-demand retrofits. A future run of the authorship skill against its own existing module is the path to `green`.

---

## Network of volumes (as of 0.1.0)

```
      obsidian-notes-region
             │ │ │
             │ │ └── outbound_refs-as-citation (face) ── csharp-source-region
             │ │                                                │
             │ └───── outbound_refs-as-citation (face) ── regency-folder-region
             │                                                  │
             └────── placement-set ──── vacuum-reading-region ──┘

  4 volumes (3 adapters + 1 metric), 4 shared structural elements, 4 datum families
```

The network grows by running authorship skills against new targets. Per-volume reports land under `.cube/reports/network/` after `cube network`.

---

## Troubleshooting

**`cube: command not found`** — install didn't register the console script. Try `pip install -e . --force-reinstall`; confirm you're in the venv you expect with `which cube`.

**`ModuleNotFoundError: No module named 's3'`** — `pip install -e .` was run from the wrong directory. Install must be run from the repo root (where `pyproject.toml` lives).

**`cube proofs` prints `reality_check: ... anomalies`** — one of the manifest-declared modules can't import. Usually means a `.claude/skills/` skill was deleted without updating `.claude/skills/_manifest.yaml`. Either restore the skill or remove the entry.

**`[FAIL] adapters/<name>: X/4 proofs`** — one or more proofs failed. The line below each FAIL shows which (pressure / datum / corrective / dual_test) and the failure reason. Common causes: moved fixture, drift between adapter's `PROOF` declaration and its test module, corrective `before == after` (the default correction event doesn't shift anything against the fixture).

**`audit_library()` returns `{"passed": false}`** — one of the services library modules has a broken `run_self_test`. Run the service's module directly (e.g. `python -m s3.cubes.adapters.services.csharp_usings`) to see which assertions failed.

**Windows path issues in `cube bootstrap`** — the bootstrap walks the target tree with `Path.rglob`. Very large trees (>50K files) trigger a guard that caps scan at 20K; the counts are still representative. Mounted network drives may be slow; prefer local clones.

---

## Repository layout (what ships in this package)

```
pyproject.toml                     # coverage-cube 0.1.0 + console script
primitives.py                      # Bott=8, FANO=7, V=3, S_V=12, C_V=28
LICENSE                            # proprietary
RELEASE_NOTES.md                   # v0.1.0 milestone notes
s3/
  __init__.py
  combinatorial_complex.py         # base cell complex (used by cube)
  cubes/                           # the cube itself
    __init__.py
    adapters/                      # SourceAdapter library + services
    metrics/                       # MetricPlugin library
    datums/                        # datum pack library + staleness reference
    stores/                        # CandidateStore (in-memory)
    extractors/                    # chunk / link / metadata
    placement/                     # suggest / decide / emit
    profile/                       # Profile Card + axis proposer
    proofs/                        # four-proof harness (adapter / metric / datum_pack)
    ir/                            # KnowledgeIR (canonical in-memory reduction)
    skill_tests/fixtures/          # carved fixtures for all green modules
    manifest.py                    # loads + validates _manifest.yaml
    skill_support.py               # contextual-skill helpers
    dashboard.py                   # rendering helpers
    sweep.py                       # B_3 orbit-integration
    cli.py                         # the `cube` console script
    run_proofs.py                  # four-proof harness runner (also: `cube proofs`)
    run_network.py                 # network-of-volumes render (also: `cube network`)
    README.md                      # this file
.claude/skills/                    # authorship skills (the library)
  _manifest.yaml                   # audit surface: active skills + exports
  cube/SKILL.md                    # workflow skill
  adapter-design/SKILL.md
  metric-design/SKILL.md
  datum-design/SKILL.md
  observation-design/SKILL.md
  dashboard-design/SKILL.md
  sweep-design/SKILL.md
  transducer-design/SKILL.md       # stub
```

Runtime state (never tracked) lives under `.cube/` — see `.gitignore`.

---

## What comes next

The planned eval + system-instruction layer sits above the cube and delivers:

- `/translate` skill — anticorruption vocabulary layer (typed wiki per project UL)
- `/engage` skill — per-engagement contract authoring with SMART + KPI triads
- Routine layer — `DispatcherRoutine` / `CollectorRoutine` / `PresenterRoutine`
- KPI presenter — multi-dimensional reports as signed-chain reductions
- Schema-as-truth-enforcer — machine-checkable required fields; rejections are signed events
- Extend-don't-rewrite tool-scaffold primitive — lag-miss-driven tool growth

Three further doctrines ship with that layer: Anticorruption, Contextual-Layer, Extend-Don't-Rewrite.

---

## References

- Workflow skill: [`.claude/skills/cube/SKILL.md`](../../.claude/skills/cube/SKILL.md)
- Reference adapter skill (generative, contextual): [`.claude/skills/adapter-design/SKILL.md`](../../.claude/skills/adapter-design/SKILL.md)
- Manifest: [`.claude/skills/_manifest.yaml`](../../.claude/skills/_manifest.yaml)
- Constants: [`primitives.py`](../../primitives.py)
- Release notes: [`RELEASE_NOTES.md`](../../RELEASE_NOTES.md)
- License: [`LICENSE`](../../LICENSE)
