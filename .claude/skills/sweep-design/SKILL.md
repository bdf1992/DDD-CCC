---
name: sweep-design
description: Use this skill when the user wants the LLM to author a new Coverage Cube orbit-integrated sweep — a module that applies a group action (B_3 hyperoctahedral, cyclic, dihedral, custom) over cube state and emits per-frame anisotropy signals + orbit-integrated invariants. This skill is generative, contextual, and bound to the contextual-skill pattern (create-datum + semantic-balance obligations, four-piece protocol). Sweeps reveal symmetry-adapted structure — what changes across group action vs what stays invariant. Invoke when the user says "add a sweep", "sweep <X> over the cube", "check anisotropy of <Y>", "orbit-integrate <Z>", "author a group-action sweep". Do NOT invoke for one-shot measurements — that is `metric-design`. Keywords: sweep design, orbit sweep, B_3 sweep, hyperoctahedral, group action, anisotropy, orbit integrated, symmetry adapted, frame dynamics.
---

# Sweep-Design Skill — Contextual, Generative, Orbit-Integrated

A module-authoring skill under the contextual-skill pattern. Authors a new orbit-integrated sweep as a **contextual move on the cube** — apply a group action to cube state, emit per-frame anisotropy signals + orbit-integrated invariants, ship four proofs + network-extension report + balance check.

| Skill | Answers |
|---|---|
| `cube` | Run existing sweeps at ingest. |
| `sweep-design` | **Author a new group-action sweep.** |
| `metric-design` | One-shot measurement over cube state. |
| `observation-design` | Chunk-stream observer during ingest. |

## Where sweeps sit (symmetry-adapted reveal)

The 3-cube's symmetry group is `B_3` (hyperoctahedral, 48 elements = 3! × 2³). An orbit-integrated sweep applies every group element to the current IR, records the per-frame signal, and decomposes the result into:

- **Invariant component** — signal that survives every group element. The structural baseline.
- **Anisotropic component** — signal that depends on which frame you look through. The asymmetry pointer.

Reference purposes:
- **B_3 orientation sweep** — applies all 48 orientations to a placement; surfaces frame-dependent readings that otherwise hide behind an implicit canonical frame.
- **cyclic sweep (rank-2 face rotations)** — cycles face labels; reveals which datums are face-order-dependent.
- **dihedral sweep** — flips + rotates; catches chirality-sensitive signals.

`s3/cubes/sweep.py` ships the B_3 machinery; a new sweep authors on top of it or introduces a different group.

## The two obligations

1. **create-datum** — the sweep must emit at least one typed datum per invocation: either an invariance datum (*"signal X is invariant across group"*) or an anisotropy datum (*"signal Y differs by factor F across group"*). Silent sweeps refused.
2. **semantic-balance** — the sweep must run over a balanced subset of the group. Running on a single group element is not a sweep. Running over an exponentially-large group without sampling is unbalanced.

## The four framed pieces

### Piece 1 — Requirements for the LLM (the contract)

- **Protocol** (already partly in `s3/cubes/sweep.py`; extend to a formal SweepPlugin):
  ```python
  class SweepPlugin(Protocol):
      name: str
      fires_at: frozenset[str]         # {"ingest", "sweep"}
      group: str                        # "B_3" | "cyclic_6" | "custom_<name>"
      def sweep(self, ir: KnowledgeIR) -> SweepResult: ...
  ```
- **`SweepResult`**: `name`, `invariants` (dict), `anisotropy` (dict of per-frame deltas), `summary`.
- **PROOF**: pressure claim names the symmetry-adapted signal; datum_runner emits `sweep_invariant` or `sweep_anisotropy` instances with evidence.
- **Test module**: run against a fixture IR; assert invariant preservation + expected anisotropy.
- **Fixture**: IR with a placement configuration known to break a specific symmetry (anisotropy expected).

### Piece 2 — Generative engine (contextual authorship flow)

**Step 0 — Identify the symmetry candidate.** What symmetry does the user suspect the data should / should not have? Name the group + the signal axis.

**Step 1 — Read cube context.** Placement load distribution shapes the sweep — on a near-vacuum cube, many frames produce identical readings; on a dense cube, small shifts matter.

**Step 2 — Diff against existing sweeps.** `sweep.py` already ships B_3 orbit machinery. Confirm the new sweep is distinct in group or signal-axis, not a rerun.

**Step 3 — Choose / declare the group.** `B_3` (48 elts), `cyclic_N`, `dihedral_N`, `Z_2^n`. Small is better — exponential groups need sampling, which is harder to verify.

**Step 4 — Author the sweep module.** `s3/cubes/sweeps/<name>.py`. Implement `sweep(ir)` returning a `SweepResult`. Use `sweep.py`'s group machinery where applicable.

**Step 5 — Ship PROOF.** Pressure claim names what anisotropy the sweep reveals. Datum runner emits one invariant + one anisotropy datum per sweep run.

**Step 6 — Build fixture.** IR configured so anisotropy is expected (broken symmetry) AND invariants are known.

**Step 7 — Semantic-balance check.** Is the sweep iterating over all 48 elements, or sampling? If sampling, are the sampled elements representative? Call `balance_check` on the sampled subset.

**Step 8 — Register + verify.** Manifest + run_proofs (`run_sweep_proofs` to be wired).

**Step 9 — Network-extension report.** Volume added = a **symmetry-adapted region** of the cube — the projection of cube state onto the invariant / anisotropic axes of the sweep's group.

### Piece 3 — Harness (partly on disk)

- `s3/cubes/sweep.py` — B_3 machinery + orbit-integration primitives.
- `s3/cubes/proofs/sweep_proof.py` (to be authored with first sweep).
- `s3/cubes/run_proofs.py` — needs `run_sweep_proofs`.

### Piece 4 — Reference

`s3/cubes/sweep.py`'s B_3 orbit-integration — not yet a SweepPlugin. The first sweep authored under this skill should formalize it as a SweepPlugin + ship four proofs.

## Self-extension pattern

Sweeps may need group-theoretic helpers: element enumeration, orbit coset representatives, invariance testers. Author under `s3/cubes/sweeps/group_ops/<name>.py`. No speculative group helpers.

## Refusal rule

> *"I can describe a proposed sweep, but I cannot register it until it ships four proofs AND emits at least one invariant AND one anisotropy datum AND passes a semantic-balance check. A sweep that returns only a single frame's reading is not a sweep — refused."*

## Anti-patterns (refused on sight)

- **Single-frame "sweep"** — no group iteration; not a sweep.
- **Group enumeration without invariance check** — sweep must separate invariant from anisotropic.
- **Group explosion without sampling rationale** — running 10^9 elements without a stated sampling strategy.
- **Mutates IR during sweep** — sweeps are read-only over the IR; side-effects refused.
- **No fixture breaking the symmetry** — fixture must produce non-trivial anisotropy or the proof is vacuous.
