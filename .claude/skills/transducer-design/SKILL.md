---
name: transducer-design
description: Use this skill when the user wants the LLM to author a new Coverage Cube Knowledge Shape transducer — a module that reshapes `KnowledgeIR` into an external representation (Markdown doc bundle, Obsidian vault, Greenfield JSONL, vector store, JIRA tickets, Postgres rows, Google Drive folder, ...) with a **preservation report** naming what was preserved exactly / via sidecar / via projection / lossy. This skill ships as a STUB; the full skill will land in a later release. Invoke when the user says "emit <Y> to <storage>", "export cube to <Z>", "transduce KnowledgeIR to <W>", "author a Knowledge Shape transducer". Keywords: transducer design, knowledge shape, preservation report, exact/sidecar/projected/lossy, KnowledgeIR export, representation change.
---

# Transducer-Design Skill — STUB

**Status**: STUB. The full skill lands with the Knowledge Shape Engine in a later release. This file exists now so the module-skill library is complete at the naming level and `_manifest.yaml::authorship_skills` can reference it.

## What the full skill will do

Authors `TransducerPlugin` modules — pure functions that consume `KnowledgeIR` and emit an external representation with a per-field **preservation report**:

| Preservation mode | Meaning |
|---|---|
| `exact` | bit-for-bit round-trip |
| `sidecar` | reversible with an auxiliary file (e.g. YAML metadata alongside markdown body) |
| `projected` | one-way lossy projection, mathematically characterized (e.g. continuous measurement → histogram) |
| `lossy` | one-way drop, user-acknowledged (e.g. body → summary) |

Every transducer invocation must produce both the output artifact AND the preservation report — the report IS the product alongside the output. Without the report, the representation change is silent structure loss.

## Where transducers sit

Transducers are the inverse of adapters: adapters bring external representations INTO `KnowledgeIR`; transducers emit `KnowledgeIR` BACK out to external representations. The invariant is the loop:

```
external knowledge → SourceRecord → placement → KnowledgeIR → transducer →
    shaped output + preservation report
```

This skill is the authorship gate for the final step.

## The two obligations — inherited

When this stub is opened, the skill inherits the contextual-skill pattern:

1. **create-datum** — every transduction produces a typed `preservation_summary` datum citing what was preserved at each mode. The datum IS the preservation report.
2. **semantic-balance** — the transducer must project cube state proportionately into the target representation. If 80% of records would collapse to `lossy` while 20% round-trip, the transducer surfaces that and asks before executing.

## The four framed pieces (outline)

When this skill is fleshed out, it will follow the same four-piece pattern as `adapter-design` / `metric-design` / `observation-design` / `dashboard-design` / `sweep-design`:

- **Piece 1 — Requirements**: `TransducerPlugin` Protocol, `RenderResult`, `PreservationReport`, PROOF, test module, fixture.
- **Piece 2 — Generative engine**: read target representation schema → read cube context → diff against existing transducers → author module + preservation-mode annotations per field → fixture → test.
- **Piece 3 — Harness**: `s3/cubes/transducers/base.py` + `s3/cubes/proofs/transducer_proof.py` + `run_transducer_proofs` in `run_proofs.py`.
- **Piece 4 — Reference**: first candidate is `markdown_bundle` — transduce `KnowledgeIR` to a wiki-shaped markdown tree that the `markdown` or `obsidian` adapter can re-ingest (round-trip test = `exact` mode for the body field).

## Relationship to the `knowledge-shape` workflow skill

A future `knowledge-shape` workflow skill runs transducers; this skill (`transducer-design`) authors them. Same split as `cube` vs `adapter-design`.

## Refusal rule (active now even in stub form)

> *"I can describe a proposed transducer, but I cannot register it until this skill graduates from STUB. Authorship attempts against this stub should defer or call `knowledge-shape` when it lands."*

## References

- Preservation doctrine: Datum-Preserving Knowledge Loop
- Pattern references: `adapter-design`, `metric-design`, `observation-design`, `dashboard-design`, `sweep-design` SKILL.md files for the shape this skill will adopt.
