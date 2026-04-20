"""
s3.cubes.metrics — Metric plugins that read cube state.

A MetricPlugin computes a structured reading of a KnowledgeIR: coverage per
rank, vacuum cells, frustrated edges, rank-weighted richness, etc. Metrics
are raw reads — they do NOT emit datums directly. Datums compose metrics
+ adapter content into actionable claims.

Each plugin declares `fires_at: frozenset[str]` — the lifecycle points at
which it should be invoked (ingest / accept / reject / modify / sweep / ci).
Consistent with the shift-left / CI timing extension point.

First four plugins:
    CoverageMetric    — cell presence per rank (line/function/branch equivalents)
    VacuumMetric      — empty cells per rank (untested territory)
    FrustrationMetric — H^0-style incoherence on incident edges + faces
    RichnessMetric    — rank-weighted concept density
"""

from s3.cubes.metrics.base import (
    MetricPlugin,
    MetricResult,
    MetricRegistry,
)
from s3.cubes.metrics.coverage import CoverageMetric
from s3.cubes.metrics.vacuum import VacuumMetric
from s3.cubes.metrics.frustration import FrustrationMetric
from s3.cubes.metrics.richness import RichnessMetric

__all__ = [
    "MetricPlugin", "MetricResult", "MetricRegistry",
    "CoverageMetric",
    "VacuumMetric",
    "FrustrationMetric",
    "RichnessMetric",
]
