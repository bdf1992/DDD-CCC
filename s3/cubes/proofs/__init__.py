"""
Proofs — the four-proof harness enforcing the module-ship discipline.

Every module-skill must ship with:
  1. pressure  — a claim loggable against specific cells / candidates / datums
  2. datum     — at least one datum computed from data (not hand-authored prose)
  3. corrective — a hook that measurably shifts output when a user correction fires
  4. dual_test — code TDD passes AND skill-vs-code agreement test passes

Public surface:
    ProofResult, ProofReport, ProofStatus (enum-like strings)
    ProofDeclaration — what a module provides to be provable
    verify_adapter, verify_metric, verify_datum_pack — per-kind runners
"""
from s3.cubes.proofs.harness import (
    ProofResult,
    ProofReport,
    ProofDeclaration,
    ProofKind,
    PROOF_KINDS,
    green_report,
)
from s3.cubes.proofs.adapter_proof import verify_adapter
from s3.cubes.proofs.metric_proof import verify_metric
from s3.cubes.proofs.datum_proof import verify_datum_pack

__all__ = [
    "ProofResult",
    "ProofReport",
    "ProofDeclaration",
    "ProofKind",
    "PROOF_KINDS",
    "green_report",
    "verify_adapter",
    "verify_metric",
    "verify_datum_pack",
]
