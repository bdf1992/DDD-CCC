"""
Axis proposer — reads distributions over already-extracted signals and proposes
V=3 axes with per-axis evidence citations.

Signals it reads (all produced by adapters + extractors + measure):
    - source_type distribution
    - classified type distribution (from measure.classify_type)
    - tag distribution (from canonical metadata)
    - path_parts[0] distribution (top-level directory)
    - heading first-token distribution (for prose sources)

Picks three signals with the highest decomposition entropy + at least 3 bins,
orders them by information content, and packages each as an AxisSpec with
citations back to contributing records.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from primitives import V
from s3.cubes.profile.invariants import validate_axis_proposal


@dataclass
class AxisSpec:
    """One proposed axis.

    slot          : 0..V-1 — position in the cube convention
    name          : default (user can rename on refinement)
    description   : one-line of what this axis distinguishes
    source_signal : name of the signal this axis reads (source_type / tag / ...)
    bins          : list of {label, count, citations} — the distribution we saw
    entropy       : bits of entropy over the distribution
    """
    slot: int
    name: str
    description: str
    source_signal: str
    bins: list[dict] = field(default_factory=list)
    entropy: float = 0.0


@dataclass
class AxisProposal:
    """The full V-axis proposal presented to the user for refinement."""
    axes: list[AxisSpec] = field(default_factory=list)
    rejected_signals: list[dict] = field(default_factory=list)  # signals we considered but didn't pick

    def validation_errors(self) -> list[str]:
        return validate_axis_proposal(self)

    def is_valid(self) -> bool:
        return not self.validation_errors()


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts if c > 0)


def _bin_signal(signal_name: str, distribution: Counter, contributors: dict) -> dict:
    """Package a signal distribution as a candidate-axis descriptor."""
    bins = []
    for label, count in distribution.most_common():
        citations = list(contributors.get(label, []))[:3]  # cap citations per bin
        bins.append({"label": str(label), "count": count, "citations": citations})
    return {
        "source_signal": signal_name,
        "distribution": dict(distribution),
        "bins": bins,
        "entropy": _entropy(list(distribution.values())),
        "distinct_bins": len(distribution),
    }


def _collect_candidate_signals(candidates: list) -> list[dict]:
    """For each potential source of axis discrimination, build its descriptor."""
    from s3.cubes.measure import classify_type

    # source_type
    st_counts: Counter = Counter()
    st_cites: dict = {}
    for c in candidates:
        st_counts[c.source_type] += 1
        st_cites.setdefault(c.source_type, []).append(c.source_id)

    # classified type (intrinsic bucket)
    ct_counts: Counter = Counter()
    ct_cites: dict = {}
    for c in candidates:
        t = classify_type(c)
        ct_counts[t] += 1
        ct_cites.setdefault(t, []).append(c.source_id)

    # tags
    tag_counts: Counter = Counter()
    tag_cites: dict = {}
    for c in candidates:
        md = c.metadata or {}
        tags = md.get("tags") or []
        if isinstance(tags, list):
            for t in tags:
                tag_counts[str(t)] += 1
                tag_cites.setdefault(str(t), []).append(c.source_id)

    # top-level directory (from path_parts[0])
    dir_counts: Counter = Counter()
    dir_cites: dict = {}
    for c in candidates:
        md = c.metadata or {}
        parts = md.get("path_parts") or []
        if parts:
            d = parts[0]
            dir_counts[d] += 1
            dir_cites.setdefault(d, []).append(c.source_id)

    # heading first-token (prose only) — from record.body when title is heading-shaped
    head_counts: Counter = Counter()
    head_cites: dict = {}
    for c in candidates:
        if c.source_type not in ("markdown", "obsidian_note"):
            continue
        title = c.title or ""
        if not title.strip():
            continue
        first_tok = title.strip().split()[0].lower().strip(":.,")
        if first_tok and len(first_tok) > 1:
            head_counts[first_tok] += 1
            head_cites.setdefault(first_tok, []).append(c.source_id)

    return [
        _bin_signal("source_type", st_counts, st_cites),
        _bin_signal("classified_type", ct_counts, ct_cites),
        _bin_signal("tag", tag_counts, tag_cites),
        _bin_signal("top_level_dir", dir_counts, dir_cites),
        _bin_signal("heading_first_token", head_counts, head_cites),
    ]


def _default_name_for_signal(signal: str) -> str:
    return {
        "source_type": "source_type",
        "classified_type": "material_type",
        "tag": "tag",
        "top_level_dir": "module",
        "heading_first_token": "heading_topic",
    }.get(signal, signal)


def _default_description(signal: str) -> str:
    return {
        "source_type": "which adapter emitted the record (markdown / obsidian / greenfield)",
        "classified_type": "intrinsic type bucket (code / prose / test / spec / config / data / etc.)",
        "tag": "user-supplied tag distribution",
        "top_level_dir": "top-level directory the record lives under",
        "heading_first_token": "first token of the record's primary heading",
    }.get(signal, f"distribution over {signal}")


def propose_axes(candidates: list) -> AxisProposal:
    """Given a candidate pool, propose V=3 axes with per-axis evidence.

    Selection rule: pick the V signals with highest entropy AND >= 3 distinct
    bins AND >= 1 candidate per bin. Rejected signals are retained in the
    proposal for transparency.
    """
    descriptors = _collect_candidate_signals(candidates)

    # Filter: viable signals must have >= 2 distinct bins (binary axes are valid).
    # Preference for >=3-bin signals is expressed via entropy ranking, not a
    # hard filter — real repos often have 2-bin splits (markdown vs code) that
    # are load-bearing distinctions.
    viable = [d for d in descriptors if d["distinct_bins"] >= 2]
    nonviable = [d for d in descriptors if d["distinct_bins"] < 2]

    # Rank by entropy descending
    viable.sort(key=lambda d: d["entropy"], reverse=True)
    chosen = viable[:V]
    rejected = [
        {"source_signal": d["source_signal"], "distinct_bins": d["distinct_bins"],
         "entropy": round(d["entropy"], 4),
         "reason": "fewer than 3 distinct bins" if d["distinct_bins"] < 3 else "not top-V by entropy"}
        for d in nonviable + viable[V:]
    ]

    axes = [
        AxisSpec(
            slot=i,
            name=_default_name_for_signal(d["source_signal"]),
            description=_default_description(d["source_signal"]),
            source_signal=d["source_signal"],
            bins=d["bins"],
            entropy=round(d["entropy"], 4),
        )
        for i, d in enumerate(chosen)
    ]
    return AxisProposal(axes=axes, rejected_signals=rejected)
