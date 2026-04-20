---
name: datum-design
description: Use this skill when the user wants to define, extend, verify, or publish new datum types derived from project storage patterns, interaction patterns, cube measurements, source evidence, code structure, or semantic signals. This skill authors new datum families — it does NOT run existing datums. Invoke when the user says "define a new datum", "add a new datum type", "I want to detect <X>", "teach the cube to measure <Y>", "author a datum", "extend the datum catalog", "write a custom datum", "datum design". Also invoke when the user describes a signal they want surfaced that isn't covered by existing datums ("I want to know when prose grows faster than code", "can we detect unreferenced specs?", "flag regions with high rejection rate"). Keywords: datum design, custom datum, new datum type, datum authoring, datum pack, datum schema, datum YAML, datum validation, datum refusal rule.
---

# Datum-Design Skill — Authoring New Coverage Signals

This is the **sibling skill** to `cube`. The two split responsibilities cleanly:

| Skill | Answers |
|---|---|
| `cube` | *"What does this project measure? Ingest / place / measure / show / report."* |
| `datum-design` | *"What **new** actionable signal can this project derive from what it stores, does, and changes?"* |

A datum is a **typed, cited, actionable claim** — not a metric. Metrics read cube state. Datums compose metrics + adapter content + project context into something a human or LLM can act on directly.

## The load-bearing rule (refusal rule)

> *"I can name this proposed datum, but I cannot register it until we know what evidence proves it, what evidence disproves it, and what fields make it syntactically valid."*

A datum is invalid — and **cannot register** — unless it declares all of:

1. **Name** — snake_case identifier
2. **Family** — `staleness | composition | vocabulary | structural | meta`
3. **Tier** — `primitive | composable | complex`
4. **Description** — one-line claim
5. **Inputs** — at least one non-empty signal section (`storage_signals / interaction_signals / cube_signals / text_signals`)
6. **Semantic check** — claim + `must_have[]` list of required evidence kinds
7. **Syntactic check** — `required_fields[]` list of schema fields
8. **Output** — `severity / claim / evidence / recommended_action`
9. **Examples** — one `positive` case (should match) + one `negative` near-miss (should NOT match)
10. **Failure mode** — what goes wrong if this datum overfires or underfires

This is enforced by `validate_datum()`. The CLI surfaces every missing field when you attempt to register an incomplete datum. Without this structure, a datum is prompt lore — it cannot be run, audited, or falsified.

## The three tiers

- **Primitive** — directly checkable from raw signals (timestamps, links, paths, placement state). Examples: `doc_older_than_code`, `spec_never_implemented`, `orphan_term`, `empty_cell`.
- **Composable** — chains primitives into a richer signal. Examples: `stale_requirement_cluster`, `prose_to_code_imbalance`, `qa_pressure_without_tests`.
- **Complex** — narrativized, cited, multi-evidence claims requiring interpretation. Examples: `architectural_drift`, `domain_language_instability`, `unverified_product_claim`.

Primitives are usually authorable as **declarative YAML** (the standard composer runs them). Composable and complex datums typically attach a **Python composer** for real logic.

## Commands

```bash
# Inspect existing datums + packs
python -m s3.cubes.cli datum list
python -m s3.cubes.cli datum list --family staleness
python -m s3.cubes.cli datum list --tier primitive
python -m s3.cubes.cli datum packs
python -m s3.cubes.cli datum show staleness.doc_older_than_code

# Get a starter YAML template
python -m s3.cubes.cli datum schema > my_new_datum.yaml

# Check a YAML/JSON datum spec against the refusal rule
python -m s3.cubes.cli datum validate my_new_datum.yaml

# Register into the running registry (validates first)
python -m s3.cubes.cli datum register my_new_datum.yaml
```

## Authoring paths

### Quick-add (3 steps) — default

Use this for primitive datums with obvious semantics.

1. **Name + YAML.** Run `datum schema` to get a template; fill in name, family, tier, description, inputs, semantic_check, syntactic_check, output.
2. **Positive + negative examples.** Write one concrete matching case and one near-miss that shouldn't match. Both must be fleshed out; the refusal rule will reject empty example slots.
3. **Validate + register.** Run `datum validate` → fix any errors → `datum register`. The datum is now in the running registry.

### Full walkthrough (10 steps) — for first-time authors or complex datums

Use this for composable / complex datums, or when you're less sure what evidence is load-bearing. Invoke with `--full` (in conversation; the skill walks you through each step).

1. **Name the datum family.** Which of the five does it belong to? If none fits, don't invent a family yet — pick the closest and note the mismatch in `description`.
2. **Identify the source signals** — what raw adapter output does this datum read? (`file_modified_at`, `outbound_refs`, `tags`, `source_type`, etc.)
3. **Identify the storage patterns** — what file / path / repo conventions does it assume? Make these explicit so the datum is replayable on different repos.
4. **Identify the interaction patterns** — what placement history or user-decision state does it consume? (Many datums have empty `interaction_signals` today.)
5. **Declare semantic meaning** — the `semantic_check.claim`: one sentence that reads as a human-checkable assertion. And the `must_have[]`: every evidence kind required before the claim can be made.
6. **Declare syntactic checks** — the `syntactic_check.required_fields`: every field the emitted `DatumInstance.evidence` must carry. This is the machine-readable contract.
7. **Declare invariants** — captured in `failure_mode`: the conditions under which this datum lies. Be honest; every datum has them.
8. **Declare evidence refs** — which `cell_refs` and `source_refs` should each emitted instance carry? These are the citations downstream consumers trace.
9. **Write positive and negative examples.** Concrete, specific — "docs/guide.md (2024-01-01)" not "an old doc". If you can't write a negative example, the datum will overfire; fix the semantic_check first.
10. **Register the composer.** For declarative YAML: leave `composer` blank and use the standard composer. For Python subclass: implement `compute(datum, context) -> list[DatumInstance]` and attach it.

## The canonical YAML contract

```yaml
name: my_new_datum                    # snake_case
family: staleness | composition | vocabulary | structural | meta
tier: primitive | composable | complex
description: one-line claim

inputs:
  storage_signals: [file_modified_at, source_type, path_pattern]
  interaction_signals: [accepted_placements, rejected_placements]
  cube_signals: [cell_rank, cell_locality, incident_cells, vacuum_score]
  text_signals: [outbound_refs, terms, headings, tags]

semantic_check:
  claim: Human-readable sentence this datum asserts.
  must_have: [evidence_kind_1, evidence_kind_2]     # non-empty list

syntactic_check:
  required_fields: [source_id, field_a, field_b]    # non-empty list

output:
  severity: low | medium | high
  claim: "Template with {source_id} placeholders."
  evidence: {field_a: type_hint, field_b: type_hint}
  recommended_action: "What a person or LLM should do about this."

examples:
  positive: {...}    # one concrete case this SHOULD match
  negative: {...}    # one concrete near-miss that should NOT match

failure_mode: "What goes wrong when this datum overfires or underfires."
```

## When a user asks you to author a datum

Follow this script:

1. **Clarify the claim.** Ask: "What human-readable sentence is this datum asserting?" Don't accept vague phrasing. The answer becomes `semantic_check.claim`.
2. **Locate the evidence.** Ask: "What has to be true for us to emit this claim? What signals prove it?" The answer becomes `semantic_check.must_have`.
3. **Locate the disproof.** Ask: "What would make this claim wrong? What's a case where it would overfire?" The answer becomes `failure_mode` and shapes `examples.negative`.
4. **Draft the YAML.** Start from `datum schema` output. Fill in iteratively. If any field feels forced, stop and re-clarify with the user.
5. **Validate early, validate often.** Run `datum validate` after each draft. The CLI enumerates exactly which fields are missing or malformed.
6. **Register when green.** Run `datum register`.
7. **Refuse when incomplete.** If the user wants to skip evidence or examples, cite the refusal rule verbatim and stop.

## Do not

- **Do not invent new families** without flagging it. Five families are reserved; extensions should be consciously proposed, not snuck in.
- **Do not register datums with only natural-language descriptions.** The refusal rule is load-bearing.
- **Do not conflate metrics and datums.** Metrics count things. Datums claim things with evidence.
- **Do not write datums whose `examples.positive` matches their `examples.negative`.** Tighten the semantic check.

## References

- Datum dataclass + registry: `s3/cubes/datums/base.py`
- YAML schema loader: `s3/cubes/datums/schema.py`
- Standard declarative composer: `s3/cubes/datums/composer.py`
- Reference pack (primitive tier): `s3/cubes/datums/packs/staleness.py`
- Sibling skill: `.claude/skills/cube/SKILL.md`
