"""
Greenfield-shape signed datapoint emission.

Every placement decision (accept / reject / modify / unplace) emits a
hash-chained signed record matching Greenfield's datapoint schema:

    {
      "event_id":    "dp_<sha256-8>",
      "kind":        "cube.placement_decision",
      "decision":    "accept" | "reject" | "modify" | "unplace",
      "source_id":   "<adapter>::<hash>",
      "cell_label":  "<cube cell label>",
      "old_cell":    "<previous cell label, modify only>",
      "reasoning":   "<natural-language justification>",
      "actor":       "user" | "agent" | "system",
      "decided_at":  "<ISO 8601 UTC>",
      "prior_hash":  "<sha256 of previous datapoint, or null for genesis>",
      "local_hash":  "<sha256 of this record excluding local_hash field>",
      "schema":      "local-hash-v0"
    }

Chain: each datapoint's `prior_hash` points to the immediately preceding
record's `local_hash`. Breaks the chain if any record is altered.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if TYPE_CHECKING:
    from s3.cubes.placement.decide import PlacementDecision


SCHEMA = "local-hash-v0"
KIND = "cube.placement_decision"


@dataclass
class SignedDatapoint:
    event_id: str
    kind: str
    decision: str
    source_id: str
    cell_label: Optional[str]
    old_cell: Optional[str]
    reasoning: str
    actor: str
    decided_at: str
    prior_hash: Optional[str]
    local_hash: str
    schema: str

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "decision": self.decision,
            "source_id": self.source_id,
            "cell_label": self.cell_label,
            "old_cell": self.old_cell,
            "reasoning": self.reasoning,
            "actor": self.actor,
            "decided_at": self.decided_at,
            "prior_hash": self.prior_hash,
            "local_hash": self.local_hash,
            "schema": self.schema,
        }


def _canonical_json(d: dict) -> bytes:
    return json.dumps(d, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def _compute_local_hash(payload: dict) -> str:
    """sha256 over the canonical JSON of everything except local_hash itself."""
    body = {k: v for k, v in payload.items() if k != "local_hash"}
    return "sha256:" + hashlib.sha256(_canonical_json(body)).hexdigest()


def emit_datapoint(ir, decision, prior_hash: Optional[str] = None) -> SignedDatapoint:
    """Build a signed datapoint for a placement decision.

    If `prior_hash` is None, the preceding datapoint is looked up from
    `ir.provenance[-1].local_hash` (if any). Genesis records carry
    `prior_hash: null`.
    """
    if prior_hash is None and ir.provenance:
        prior_hash = ir.provenance[-1].get("local_hash")

    event_id_material = f"{decision.source_id}|{decision.cell_label}|{decision.decided_at}"
    event_id = "dp_" + hashlib.sha256(event_id_material.encode("utf-8")).hexdigest()[:16]

    draft = {
        "event_id": event_id,
        "kind": KIND,
        "decision": decision.kind.value,
        "source_id": decision.source_id,
        "cell_label": decision.cell_label,
        "old_cell": decision.old_cell,
        "reasoning": decision.reasoning,
        "actor": decision.actor,
        "decided_at": decision.decided_at,
        "prior_hash": prior_hash,
        "schema": SCHEMA,
    }
    local_hash = _compute_local_hash(draft)
    draft["local_hash"] = local_hash
    return SignedDatapoint(**draft)


def write_jsonl_stream(signed_records: list, path: Path) -> None:
    """Write a list of SignedDatapoint (or dicts) to a JSONL file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for r in signed_records:
            if isinstance(r, SignedDatapoint):
                r = r.to_dict()
            fh.write(json.dumps(r) + "\n")


def verify_chain(records: list) -> tuple[bool, list[str]]:
    """Verify a list of signed datapoints forms a valid hash chain.

    Returns (ok, errors). Genesis record must have prior_hash=None; every other
    record's prior_hash must equal the previous record's local_hash.
    """
    errs: list[str] = []
    for i, rec in enumerate(records):
        if isinstance(rec, SignedDatapoint):
            rec = rec.to_dict()
        expected_prior = None if i == 0 else records[i - 1].to_dict()["local_hash"] \
            if isinstance(records[i - 1], SignedDatapoint) else records[i - 1]["local_hash"]
        actual_prior = rec.get("prior_hash")
        if actual_prior != expected_prior:
            errs.append(
                f"record {i} ({rec.get('event_id')}): prior_hash={actual_prior!r}, "
                f"expected {expected_prior!r}"
            )
        recomputed = _compute_local_hash(rec)
        if rec.get("local_hash") != recomputed:
            errs.append(
                f"record {i} ({rec.get('event_id')}): local_hash mismatch "
                f"(stored {rec.get('local_hash')!r}, recomputed {recomputed!r})"
            )
    return (not errs, errs)
