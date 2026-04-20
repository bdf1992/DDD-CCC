# services — Pluginable Adapter Services

The library the `adapter-design` skill composes adapters from. Grows on-demand. Seeded minimal on purpose.

## What a service IS

A *service* is a small, pure, composable module that adapters reuse. Each service module lives at `s3/cubes/adapters/services/<name>.py` and satisfies:

1. **Pure where possible.** `str → list[str]`, `bytes → dict`, etc. No network. No file I/O unless the service is explicitly an I/O service (rare; name it `io_<x>`). Side-effect-free is the default.
2. **Typed signatures.** Annotated inputs and outputs. Callers compose without ambiguity.
3. **Module-level `SERVICE: ServiceMetadata`.** Declares:
   - `name` — short lowercase, unique in the library
   - `purpose` — one-line
   - `inputs` — shape of what it accepts
   - `outputs` — shape of what it produces
   - `example` — inline demonstration
   - `used_by` — tuple of adapter names importing this service
4. **`run_self_test() -> dict`.** Returns `{"passed": bool, "summary": str, "failures": list}`. Called by `audit_library()` before every adapter-design run.
5. **Does one thing. Composes with others. Does not orchestrate.** If your service imports three other services, it's an adapter fragment — push it into the adapter module, not here.

The `wikilink_extractor` service in `_seed.py` is the minimal complete example. Diff new services against it.

## How the library grows

**Seeded minimal.** Only `_seed.py` ships on day zero. That is the entire library. The `adapter-design` skill is responsible for extension.

**Grown by adapter-design runs.** When the skill runs against a target repo and encounters a source system the library doesn't cover:

1. The skill authors a new service module `<name>.py` here.
2. Its `SERVICE` declaration + `run_self_test` ship with it.
3. `REGISTRY` in `__init__.py` gets a new entry.
4. The adapter being generated imports and uses the new service in the same run.

**No speculative services.** Every service authored must be consumed by the adapter authored in the same skill run. Services without consumers are not admissible — they rot without use.

**Bricks, not migrations.** When a later run finds a near-miss (say, a wikilink variant that differs from Obsidian's), it authors a new service alongside the existing one — not an in-place refactor. The existing service keeps its `used_by` guarantees.

## The registry

`__init__.py::REGISTRY` is the canonical list of `(dotted_path, SERVICE)` pairs. `audit_library()` walks it, runs each `run_self_test`, and reports aggregate health. The adapter-design skill MUST call `audit_library()` and refuse to proceed if any service fails.

## Not a general-purpose library

This is not `commonmark-parser` or `sql-parser` or `nlp-utils`. It is *the services that adapter-design authored or was seeded with*. If a service is too generic to have a clear `used_by` adapter, it does not belong here — push it to the generic Python toolbox.

## Contract enforcement summary

| Rule | Enforced by |
|---|---|
| Module-level `SERVICE` | `audit_library` rejects services without it |
| `run_self_test` entrypoint | `audit_library` rejects services without it |
| Pure / typed | Reviewer judgment; tests catch side effects |
| `used_by` non-empty | adapter-design refuses to register an orphan |
| Composable, not orchestrating | adapter-design diffs against `_seed.py` shape |

## Reference

- Seed service: [`_seed.py`](_seed.py)
- Skill consumer: [`.claude/skills/adapter-design/SKILL.md`](../../../../.claude/skills/adapter-design/SKILL.md)
- Reference adapter using the service: [`obsidian_vault.py`](../obsidian_vault.py)
