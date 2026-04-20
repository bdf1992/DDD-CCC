"""
MetricPlugin Protocol + MetricResult dataclass + MetricRegistry.

Every metric plugin carries `fires_at` (lifecycle declaration) and a
`measure(ir)` method returning a MetricResult. Metrics are ADDITIVE to the
KnowledgeIR via its measurements list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Optional, TYPE_CHECKING
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

if TYPE_CHECKING:
    from s3.cubes.ir.graph import KnowledgeIR


FIRES_AT_VALUES = frozenset({"ingest", "accept", "reject", "modify", "sweep", "ci", "post-deploy", "ide"})


@dataclass
class MetricResult:
    """Output of one metric invocation.

    name          : plugin identifier
    scalars       : named scalar readings (counts, ratios, etc.)
    cell_readings : per-cell structured output (rank-colored presence, severity, etc.)
    summary       : short human-readable one-liner
    """
    name: str
    scalars: dict = field(default_factory=dict)
    cell_readings: dict = field(default_factory=dict)
    summary: str = ""
    observed_at: str = ""

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(tz=timezone.utc).isoformat()


class MetricPlugin(Protocol):
    """Every metric plugin satisfies this protocol."""
    name: str
    fires_at: frozenset[str]

    def measure(self, ir: "KnowledgeIR") -> MetricResult: ...


class MetricRegistry:
    """In-process metric registry. Plugins register on construction."""

    def __init__(self) -> None:
        self._plugins: dict[str, MetricPlugin] = {}

    def register(self, plugin: MetricPlugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"metric already registered: {plugin.name}")
        bad = set(plugin.fires_at) - FIRES_AT_VALUES
        if bad:
            raise ValueError(
                f"metric {plugin.name}: fires_at contains unknown values {sorted(bad)}; "
                f"allowed: {sorted(FIRES_AT_VALUES)}"
            )
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Optional[MetricPlugin]:
        return self._plugins.get(name)

    def plugins_firing_at(self, event: str) -> list[MetricPlugin]:
        return [p for p in self._plugins.values() if event in p.fires_at]

    def all(self) -> list[MetricPlugin]:
        return sorted(self._plugins.values(), key=lambda p: p.name)

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins


def run_all(registry: MetricRegistry, ir: "KnowledgeIR", event: str) -> list[MetricResult]:
    """Invoke every plugin whose fires_at contains the given event."""
    return [p.measure(ir) for p in registry.plugins_firing_at(event)]
