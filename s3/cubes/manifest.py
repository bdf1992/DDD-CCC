"""
Manifest — the cube's audit surface for active skills + exported modules.

The cube reads only modules declared in `.claude/skills/_manifest.yaml`.
Runtime dynamic-module-loading outside the manifest is refused. Adding a module
costs an authorship skill + four proofs + a manifest entry.

Manifest revisions (promote / retire a module-skill, change proof_status) emit
signed events into the datapoint chain — the active skill set evolves with
anchors and corrections.

Schema:
    version             : manifest schema version
    instance            : project name this manifest belongs to
    workflow_skills[]   : names of active workflow skills (must exist in .claude/skills/)
    authorship_skills[] : names of active authorship skills (must exist in .claude/skills/)
    exports:
      adapters[]          : {name, module, class, proof_status}
      metrics[]           : {name, module, proof_status}
      datum_packs[]       : {name, module, proof_status}
      sweeps[]            : {name, module, proof_status}
      observations[]      : {name, module, proof_status}
      transducers[]       : {name, module, proof_status}
      dashboard_panels[]  : {name, module, proof_status}

proof_status ∈ {"ungated", "green", "retired"}.
    ungated — module exists, proofs not yet verified by the harness.
    green   — all four proofs verified; free to list.
    retired — manifest entry kept for audit, module no longer loaded.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml


VALID_PROOF_STATUS = frozenset({"ungated", "green", "retired"})
VALID_MODULE_KINDS = frozenset({
    "adapters", "metrics", "datum_packs", "sweeps",
    "observations", "transducers", "dashboard_panels",
})


@dataclass
class ModuleEntry:
    """One exported module in the manifest."""
    kind: str                       # one of VALID_MODULE_KINDS
    name: str                       # export name, short + lowercase
    module: str                     # import path (dotted)
    class_name: Optional[str]       # class to instantiate (adapters); else None
    proof_status: str               # one of VALID_PROOF_STATUS
    extras: dict = field(default_factory=dict)

    def qualname(self) -> str:
        return f"{self.kind}/{self.name}"


@dataclass
class Manifest:
    """Parsed manifest. Source of truth for which modules the cube may load."""
    version: str
    instance: str
    workflow_skills: list[str]
    authorship_skills: list[str]
    modules: list[ModuleEntry]
    source_path: Optional[Path] = None

    def green(self, kind: Optional[str] = None) -> list[ModuleEntry]:
        """Modules with proof_status == green. Filter by kind if given."""
        return [m for m in self.modules
                if m.proof_status == "green"
                and (kind is None or m.kind == kind)]

    def by_kind(self, kind: str) -> list[ModuleEntry]:
        return [m for m in self.modules if m.kind == kind]

    def find(self, kind: str, name: str) -> Optional[ModuleEntry]:
        for m in self.modules:
            if m.kind == kind and m.name == name:
                return m
        return None

    def fingerprint(self) -> str:
        """Stable hash of the active declaration (ignores source_path)."""
        h = hashlib.sha256()
        h.update(f"Manifest/v{self.version}/{self.instance}\n".encode("utf-8"))
        for s in sorted(self.workflow_skills):
            h.update(f"W:{s}\n".encode("utf-8"))
        for s in sorted(self.authorship_skills):
            h.update(f"A:{s}\n".encode("utf-8"))
        for m in sorted(self.modules, key=lambda x: (x.kind, x.name)):
            h.update(f"{m.kind}:{m.name}:{m.module}:{m.class_name}:{m.proof_status}\n"
                     .encode("utf-8"))
        return "sha256:" + h.hexdigest()


class ManifestError(ValueError):
    """Raised on any malformed or inconsistent manifest."""


def load_manifest(path: Path | str) -> Manifest:
    """Load and validate a manifest YAML from disk."""
    p = Path(path)
    if not p.exists():
        raise ManifestError(f"manifest not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    m = _parse(data)
    m.source_path = p
    return m


def _parse(data: Any) -> Manifest:
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be a mapping")
    version = str(data.get("version") or "")
    instance = str(data.get("instance") or "")
    if not version:
        raise ManifestError("manifest: version required")
    if not instance:
        raise ManifestError("manifest: instance required")

    ws = list(data.get("workflow_skills") or [])
    auth = list(data.get("authorship_skills") or [])
    for s in (*ws, *auth):
        if not isinstance(s, str) or not s:
            raise ManifestError(f"manifest: skill entries must be non-empty strings ({s!r})")

    modules: list[ModuleEntry] = []
    exports = data.get("exports") or {}
    if not isinstance(exports, dict):
        raise ManifestError("manifest.exports must be a mapping")
    for kind, entries in exports.items():
        if kind not in VALID_MODULE_KINDS:
            raise ManifestError(f"manifest.exports: unknown kind {kind!r}")
        if entries is None:
            continue
        if not isinstance(entries, list):
            raise ManifestError(f"manifest.exports.{kind} must be a list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ManifestError(f"manifest.exports.{kind}: entries must be mappings")
            name = entry.get("name")
            module = entry.get("module")
            proof_status = entry.get("proof_status", "ungated")
            cls = entry.get("class")
            if not name or not module:
                raise ManifestError(f"manifest.exports.{kind}: name + module required")
            if proof_status not in VALID_PROOF_STATUS:
                raise ManifestError(
                    f"manifest.exports.{kind}/{name}: proof_status must be one of "
                    f"{sorted(VALID_PROOF_STATUS)}, got {proof_status!r}"
                )
            extras = {k: v for k, v in entry.items()
                      if k not in {"name", "module", "class", "proof_status"}}
            modules.append(ModuleEntry(
                kind=kind,
                name=str(name),
                module=str(module),
                class_name=str(cls) if cls else None,
                proof_status=str(proof_status),
                extras=extras,
            ))

    return Manifest(
        version=version,
        instance=instance,
        workflow_skills=ws,
        authorship_skills=auth,
        modules=modules,
    )


def diff_manifest(old: Manifest, new: Manifest) -> dict:
    """Structured diff suitable for signed revision events."""
    def index(m: Manifest) -> dict[str, ModuleEntry]:
        return {f"{e.kind}/{e.name}": e for e in m.modules}

    old_idx, new_idx = index(old), index(new)
    added = sorted(set(new_idx) - set(old_idx))
    removed = sorted(set(old_idx) - set(new_idx))
    changed: list[dict] = []
    for key in sorted(set(old_idx) & set(new_idx)):
        a, b = old_idx[key], new_idx[key]
        fields = {}
        for f in ("module", "class_name", "proof_status"):
            if getattr(a, f) != getattr(b, f):
                fields[f] = {"old": getattr(a, f), "new": getattr(b, f)}
        if fields:
            changed.append({"module": key, "fields": fields})
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "skills": {
            "workflow_added": sorted(set(new.workflow_skills) - set(old.workflow_skills)),
            "workflow_removed": sorted(set(old.workflow_skills) - set(new.workflow_skills)),
            "authorship_added": sorted(set(new.authorship_skills) - set(old.authorship_skills)),
            "authorship_removed": sorted(set(old.authorship_skills) - set(new.authorship_skills)),
        },
        "old_fingerprint": old.fingerprint(),
        "new_fingerprint": new.fingerprint(),
    }


def reality_check(manifest: Manifest, skills_dir: Path | str,
                  module_importable: bool = False) -> list[str]:
    """Diff the manifest against filesystem reality.

    Returns a list of human-readable anomalies. Empty list = clean.
    - Every declared workflow/authorship skill must have a SKILL.md on disk.
    - Every declared module must import cleanly (if module_importable=True).
    """
    skills_dir = Path(skills_dir)
    anomalies: list[str] = []

    for s in (*manifest.workflow_skills, *manifest.authorship_skills):
        skill_file = skills_dir / s / "SKILL.md"
        if not skill_file.exists():
            anomalies.append(f"skill declared but missing on disk: {s} "
                             f"(expected {skill_file})")

    if module_importable:
        for m in manifest.modules:
            if m.proof_status == "retired":
                continue
            try:
                importlib.import_module(m.module)
            except Exception as e:
                anomalies.append(f"module {m.qualname()} not importable: "
                                 f"{m.module} ({type(e).__name__}: {e})")

    return anomalies


def revision_event(old: Manifest, new: Manifest,
                   reason: str, prior_hash: Optional[str] = None) -> dict:
    """Build a Greenfield-shape signed revision event (caller signs it)."""
    diff = diff_manifest(old, new)
    payload = {
        "kind": "manifest_revision",
        "instance": new.instance,
        "version": new.version,
        "reason": reason,
        "diff": diff,
        "observed_at": datetime.now(tz=timezone.utc).isoformat(),
        "prior_hash": prior_hash,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["local_hash"] = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    return payload


# --- CLI entry (python -m s3.cubes.manifest) --------------------------------

if __name__ == "__main__":
    import argparse

    root = Path(__file__).resolve().parents[2]
    default_manifest = root / ".claude" / "skills" / "_manifest.yaml"
    default_skills = root / ".claude" / "skills"

    ap = argparse.ArgumentParser(description="Cube manifest loader / checker")
    ap.add_argument("--path", default=str(default_manifest))
    ap.add_argument("--skills-dir", default=str(default_skills))
    ap.add_argument("--check-imports", action="store_true")
    args = ap.parse_args()

    m = load_manifest(args.path)
    print(f"manifest: {m.source_path}")
    print(f"instance: {m.instance}  version: {m.version}")
    print(f"fingerprint: {m.fingerprint()}")
    print(f"workflow skills:   {m.workflow_skills}")
    print(f"authorship skills: {m.authorship_skills}")
    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for e in m.modules:
        by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
        by_status[e.proof_status] = by_status.get(e.proof_status, 0) + 1
    print(f"modules: {len(m.modules)} total")
    for k, v in sorted(by_kind.items()):
        print(f"  {k}: {v}")
    print(f"proof_status: {dict(sorted(by_status.items()))}")
    anomalies = reality_check(m, args.skills_dir, module_importable=args.check_imports)
    if anomalies:
        print(f"\nreality_check: {len(anomalies)} anomalies")
        for a in anomalies:
            print(f"  - {a}")
    else:
        print("\nreality_check: clean")
