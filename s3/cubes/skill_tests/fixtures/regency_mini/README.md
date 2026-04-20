# regency_mini

Carved fixture for the `regency` adapter proofs. A small regency-style folder tree.

**Regency folders** (3):

| Folder | Cross-refs (outbound_refs) | Resolved? |
|---|---|---|
| REGENCY-001-root | — | — |
| REGENCY-002-consumer | REGENCY-001 | yes (declared) |
| REGENCY-003-orphan | REGENCY-999 | **no (vacuum)** |

**Declared regencies** (3): REGENCY-001, REGENCY-002, REGENCY-003.

**Expected unresolved_regency_dep** (1): REGENCY-999.

**Proof expectations**:
- `pressure` event: `witness.unresolved_regency_refs == ["REGENCY-999"]`, 1 cell_candidate.
- `datum` runner: 1 instance of `unresolved_regency_dep`, evidence cites source_id + referring_regency=REGENCY-003.
- `corrective` whitelisting `REGENCY-999`: before=1, after=0.
- `dual_test`: code tests green (≥10 assertions), `run_skill_test` reload + rerun green.
