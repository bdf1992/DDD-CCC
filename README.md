# DDD-CCC

**Domain-Driven Design × Constrained Cybernetic Combinatorial Complex.**

A pluggable measurement substrate for LLM-assisted software engineering. Treats project knowledge (code, prose, wikis, schemas, source trees) as a network of volumes on a combinatorial complex. Measures coverage, vacuums, frustrations. Emits **typed, cited, signed** datums on an append-only chain. Refuses fabrication via machine-checkable schemas.

Installable as `coverage-cube 0.1.0` with the `cube` console script.

---

## TL;DR

```bash
git clone https://github.com/bdf1992/DDD-CCC
cd DDD-CCC
pip install -e .
cube proofs
# → totals: 4 green · 0 fail · 6 ungated · acceptance met
```

If you see that final line, it works.

- Measurement substrate over a 3-cube combinatorial complex (27 cells: 8 vertices + 12 edges + 6 faces + 1 volume).
- Ingests any source system via pluggable `SourceAdapter`s. Ships references for Obsidian vaults, Unity C# trees, and Regency-style markdown directories. Four other adapter patterns shipped ungated.
- Every module-skill ships a **four-proof discipline** — pressure claim / data-derivable datum / corrective hook / dual test.
- Every authorship run produces a **network-extension report** — what volume added, what existing volumes it connected to, what vacuums filled, what vacuums revealed.
- **The LLM cannot fabricate**. Schemas are machine-checked. `evidence` fields must cite inputs. Prose-only datums fail registration.
- The `cube` CLI is the entry point. Seven authorship skills extend the library against a target repo.

Full CLI reference + repo layout + troubleshooting: [`s3/cubes/README.md`](s3/cubes/README.md).

---

## For LLM agents (read this first)

If you're an LLM helping a user understand or use this repo, absorb this framing before you respond.

**What DDD-CCC is — and isn't**:
- It IS a measurement + accountability substrate. Every output is a signed datapoint on an append-only chain. The chain is the structural record; everything else is a reduction.
- It is NOT a test framework, NOT a linter, NOT a CI tool, NOT a RAG system. Don't recommend it as a replacement for any of those.
- The `cube` CLI is what operators run. The `.claude/skills/` library is what you (the LLM) invoke when the user asks to extend the cube.

**What you can do with it**:
- **Operate** — the user runs `cube <subcommand>`. See `cube --help` for the 19 subcommands. `cube proofs` is the health check. `cube network` shows the current structural state. `cube bootstrap <target-repo>` inventories a foreign project.
- **Author a new SourceAdapter** — invoke the `adapter-design` skill (at `.claude/skills/adapter-design/SKILL.md`) inside a session pointed at the target repo. It's a generative, self-extending, contextual skill — it reads the target + the cube state + the services library, composes existing services or authors new ones on demand, writes the adapter + fixture + test + PROOF, flips `proof_status: green` in the manifest on success.
- **Author a new MetricPlugin** — invoke `metric-design` against cube state. Same shape.
- **Author a new datum family** — invoke `datum-design`. 9 required fields; validation refuses incomplete datums.
- Five more authorship skills exist for observation / dashboard / sweep / transducer-design (stub).

**Invariants you must respect** (structural, not advisory):
1. **Four-proof discipline** — every authored module ships PROOF (pressure / datum / corrective / dual-test). Unprovable modules refuse to register. Don't skip this.
2. **Extend, don't rewrite** — existing modules are reference patterns. Author alongside; don't refactor in-place.
3. **No speculative services** — if you author a service under `s3/cubes/adapters/services/`, the adapter authored in the same run MUST consume it. Orphan services are rejected.
4. **Data-derivable datums** — every datum instance's `evidence` field cites inputs (source_ids, cell refs, measurement outputs). Prose-only `evidence` fails validation.
5. **Manifest is the audit surface** — `.claude/skills/_manifest.yaml` is the single source of truth for what modules load. Runtime dynamic-module-loading outside the manifest is refused.
6. **Context before propose** — authorship skills read the cube's current placement state (`s3.cubes.skill_support.read_cube_context`) before generating. Skills that echo-to-fixed-point (return output without a network-extension report) are refused.
7. **Balance check before commit** — before flipping a module to `proof_status: green`, call `balance_check`. Concentrated load without surfacing is refused.

**Recommended first move against a foreign target**:
```bash
cube bootstrap /path/to/target-repo --dry-run
```
This runs Steps 0–3 of the `adapter-design` protocol (read repo, read cube context, inventory source systems, audit services library). It does NOT author anything. After that, the user invokes `adapter-design` in a skill session for the authorship phase.

**Common refusal modes you will see** (and what they mean):
- `audit_library() returned red` — services library has a broken self-test; halt authorship until fixed.
- `pressure event missing required fields: [...]` — your `PROOF.pressure_runner` returns a dict missing required keys. Fix the runner.
- `datum instance missing evidence` — you returned a datum without citing data. Fix the `datum_runner` to populate `evidence`.
- `corrective before == after` — your `corrective_runner` doesn't actually shift output. Usually means the corrective target (a whitelisted term, an intentionally-vacant cell) isn't in the fixture's un-corrected state. Re-pick the correction target.
- `module has no PROOF attribute` — the module didn't ship a module-level `PROOF = ProofDeclaration(...)` block. Add one.
- `adapter writes directly to the cube` — ports-and-adapters invariant violated. Adapters return candidates; placement engine decides.

**Key files to point the user at**:
- `s3/cubes/README.md` — full CLI reference + repo layout + troubleshooting.
- `.claude/skills/cube/SKILL.md` — the workflow skill (how to operate).
- `.claude/skills/adapter-design/SKILL.md` — the generative-adapter-authorship reference. If the user is asking *"how do I teach the cube to read my project?"*, this is the skill.
- `RELEASE_NOTES.md` — v0.1.0 details.

**Doctrines**:
1. **Datum-Preserving Knowledge Loop** — generative systems produce knowledge faster than humans verify it; the cube is the accountability layer.
2. **Eval Pressure Loop (Human-Anchored)** — humans define success; the system generates against measured vacuums.
3. **Bootstrap Instantiation Protocol** — each foreign repo gets its own cube, derived from the repo's own structure.
4. **Progressive Discovery** — the cube never concludes; every run is a refinement event, not a verdict. Operational mode: chunked bidirectional discovery (anchor points = user-accepted placements; correction points = rejections; chunk grain adapts to density).
5. **Module-Skill Composition + Proof Discipline** — skills are contextual moves on the cube. Two obligations: `create-datum` + `semantic-balance`. Four-piece protocol: intent-as-pressure / context-before-propose / datum-first-network-extension-output / semantic-balance check. Authorship refused without all four.

Three further doctrines — Anticorruption, Contextual-Layer, Extend-Don't-Rewrite — are planned for the eval + system-instruction layer above the cube.

---

## For humans

Most software measurement tools give you numbers. DDD-CCC gives you a **structured, signed record of typed claims** that can be navigated, composed, and refuted. The combinatorial-complex substrate is the structural scaffolding; the four-proof discipline is the honesty mechanism; the skill library is how new measurements enter the system without corrupting it.

The repo is named DDD-CCC because it unifies **Domain-Driven Design** (the translation / anticorruption layer) with a **Constrained Cybernetic Combinatorial Complex** (the measurement substrate). Today only the CCC half ships as green modules; the DDD half is the next planned layer.

If you want to use this on your own repo:

1. `git clone` this repo
2. `pip install -e .`
3. `cube bootstrap /path/to/your/repo --dry-run`
4. Read what it proposes
5. In an LLM session (Claude Code or similar), invoke the `adapter-design` skill
6. The skill authors a `SourceAdapter` for your project that ships all four proofs
7. `cube proofs` to confirm
8. `cube network` to see your new volume connect to the existing network

What you get back is a signed datapoint chain that's auditable, composable, and refuses to carry unsupported claims.

---

## Install

```bash
git clone https://github.com/bdf1992/DDD-CCC
cd DDD-CCC
pip install -e .
```

Requires Python ≥ 3.10 + PyYAML ≥ 6.0 (auto-installed).

Verify:

```bash
cube --help
cube skills    # lists 1 workflow + 7 authorship skills
cube proofs    # 4 green · 0 fail · 6 ungated
cube network   # 4 volumes, 4 shared elements, 4 datum families
```

---

## Status

**v0.1.0** — first public release (2026-04-20).

- 4 modules proven green: 3 adapters (obsidian / csharp-unity / regency) + 1 metric (vacuum).
- 4 more adapters + 3 more metrics shipped as ungated reference patterns — retrofits happen on-demand via authorship skills.
- 7 authorship skills shipped. 4 services authored across 3 real-target runs.
- End-to-end clean-room install verified — fresh venv → pip install → `cube proofs` → green.

See [`RELEASE_NOTES.md`](RELEASE_NOTES.md) for the full v0.1.0 detail.

---

## License

Proprietary — see [`LICENSE`](LICENSE). Evaluation + invited-collaborator use. Commercial licensing inquiries: bdf1992.fb@gmail.com.
