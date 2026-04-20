# csharp_unity_mini

Carved fixture for the `csharp_unity` adapter proofs. A small Unity C# tree with an internal root namespace of `CatalystCore.Sample` (arbitrary — the fixture's chosen prefix).

**Files**: 4 × `.cs`

| File | Declares namespace | Internal usings | External usings |
|---|---|---|---|
| `Root.cs` | `CatalystCore.Sample` | — | `System`, `UnityEngine` |
| `Systems.cs` | `CatalystCore.Sample.Systems` | `CatalystCore.Sample` (resolved) | `System.Collections.Generic` |
| `Orphan.cs` | `CatalystCore.Sample.Orphan` | `CatalystCore.Models.Data` (UNRESOLVED), `CatalystCore.MissingModule` (UNRESOLVED) | `UnityEngine` |
| `Clean.cs` | `CatalystCore.Sample.Clean` | `CatalystCore.Sample` (resolved) | `System`, `UnityEngine` |

**Declared namespaces** (4):
- `CatalystCore.Sample`
- `CatalystCore.Sample.Systems`
- `CatalystCore.Sample.Orphan`
- `CatalystCore.Sample.Clean`

**Expected unresolved internal-using vacuums** (2):
- `CatalystCore.Models.Data`
- `CatalystCore.MissingModule`

**Proof expectations**:
- `pressure` event: `witness.unresolved_internal_usings == ["CatalystCore.MissingModule", "CatalystCore.Models.Data"]` (sorted), 2 cell_candidates.
- `datum` runner: 2 instances of `unresolved_internal_using`, each with evidence citing its source_id + declaring_namespace.
- `corrective` whitelisting `CatalystCore.Models.Data`: before=2, after=1.
- `dual_test`: code tests pass (≥13 assertions), `run_skill_test` reloads the adapter module + rerun green.

Keep this fixture stable. Adding files or changing usings changes the expected counts — update `csharp_unity_test.py` alongside.
