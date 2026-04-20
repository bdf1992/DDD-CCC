# Coverage Cube — Release Notes

## 0.1.0 — 2026-04-20

First public distribution that can be cloned, installed, and exercised end-to-end.

### What ships

**Substrate**
- 3-cube combinatorial complex (27 cells = 8 vertices + 12 edges + 6 faces + 1 volume)
- `ElementCube` primitive (Bott=8 element-vector with presence masks)
- `KnowledgeIR` — canonical in-memory reduction of the signed datapoint stream
- Signed datapoint chain (`local-hash-v0` + `prior_hash`)

**Adapters — 3 green**
- `obsidian` — Obsidian-style vault adapter
- `csharp-unity` — Unity C# source tree adapter (176-file smoke test clean)
- `regency` — regency-style folder adapter (2-regency smoke test clean)
- Each ships module-level `PROOF` + `DEFAULT_CORRECTION_EVENT` + 4/4 proofs

**Adapters — 4 ungated reference patterns**
- `markdown`, `greenfield-jsonl`, `filesystem-code` (author-via-skill retrofits on demand)

**Metrics — 1 green + 3 ungated**
- `vacuum` — empty-cell reveal with rank decomposition (4/4 proofs)
- `coverage`, `frustration`, `richness` remain ungated reference patterns

**Services library — 4/4 green**
- `wikilink_extractor` (seed)
- `csharp_usings` + `csharp_namespace` (authored on-demand during a Unity C# run)
- `regency_refs` (authored on-demand during a regency-folder run)
- `audit_library()` gate refuses downstream authorship on any red service

**Skills — 1 workflow + 7 authorship**
- Workflow: `cube` (operate the substrate)
- Authorship: `adapter-design`, `metric-design`, `datum-design`, `observation-design`, `dashboard-design`, `sweep-design`, `transducer-design` (stub)
- All under the contextual-skill pattern: two obligations + four-piece protocol

**CLI — `cube` console script**
- Workflow: `status`, `sources`, `ingest`, `profile`, `axes`, `suggest`, `accept`, `reject`, `modify`, `coverage`, `vacuums`, `frustrations`, `richness`, `datums`, `datum`, `rag`
- Audit/authorship: `skills`, `proofs`, `network`, `bootstrap <repo>`

**Proof harness**
- `verify_adapter`, `verify_metric`, `verify_datum_pack` (per-kind four-proof runners)
- `run_proofs.py` (a.k.a. `cube proofs`) walks the manifest + runs proofs + writes witness artifacts
- Required fields per kind enforced: adapter pressure events carry `{adapter_name, cell_candidates, witness}`; metric pressure events carry `{metric_name, cells, threshold, fires_at}`; datum evidence field required + non-empty

**Network of volumes** (as of 0.1.0)
- 4 volumes (3 adapter source-regions + 1 metric reading-region)
- 4 shared structural elements (3 outbound_refs-as-citation faces + 1 placement-set)
- 4 datum families: `unresolved_wikilink_term`, `unresolved_internal_using`, `unresolved_regency_dep`, `vacuum_cell`
- All four volumes balance-checked green

**Doctrines shipped**
- Doctrine 1 — Datum-Preserving Knowledge Loop
- Doctrine 2 — Eval Pressure Loop (Human-Anchored)
- Doctrine 3 — Bootstrap Instantiation Protocol
- Doctrine 4 — Progressive Discovery (+ operational mode: chunked bidirectional discovery)
- Doctrine 5 — Module-Skill Composition + Proof Discipline (+ contextual-skill pattern extension: two obligations + four-piece protocol + refusal-on-echo-to-fixed-point)

### What's deferred

- **Knowledge Shape Engine** — outbound transduction (`KnowledgeIR → Markdown bundle / Obsidian vault / Greenfield JSONL / vector store / ...` with preservation reports). `transducer-design` ships as a stub.
- **Hand-retrofit of ungated reference adapters + metrics** — intentional. They remain reference patterns; retrofits happen on-demand via the appropriate authorship skill when a downstream user or project needs them.
- **Direct Claude API / OpenAI-compatible backend invocation from routines** — planned; this release ships without routines.

### What's next

The planned eval + system-instruction layer above the cube delivers:

- `/translate` skill + typed wiki (Anticorruption doctrine)
- `/engage` meta-skill + engagement contract + `.engage/` directory (Contextual-Layer doctrine)
- Routine layer (dispatch / collect / present protocols + proof harness)
- KPI presenter as signed-chain reduction (on-the-loop supervision)
- Schema-as-truth-enforcer (system-level fabrication refusal)
- Extend-don't-rewrite tool-scaffold primitive

### Installation

```bash
git clone <repo-url> coverage-cube
cd coverage-cube
pip install -e .
cube --help
cube proofs     # 4 green · 0 fail · 6 ungated
```

Detailed docs: [`s3/cubes/README.md`](s3/cubes/README.md).

### License

Proprietary — see [`LICENSE`](LICENSE).
