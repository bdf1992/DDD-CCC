"""
ElementCube — the primitive element state vector.

An ElementCube holds Bott=8 values (one per F_2^3 vertex, range [-1, +1])
plus 8 presence flags (False = blind/absent). This is the atomic carrier
for the cube substrate. Every stat, trait, skill, or property lives in
one of these.

Constants forced by primitives.py:
    Bott = D^V = 2^3 = 8   (vertex count of the F_2^3 cube)
    FANO = D^V - 1 = 7     (mask; also points in Fano plane)
    V = 3                  (dimensions; locked by 2^V = V^2 - 1)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional, Sequence
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from primitives import Bott, FANO


class Affinity(IntEnum):
    """The 8 F_2^3 vertices, named with an element-cosmology labeling.

    Binary labels: each vertex is a 3-bit tag. Bit positions carry semantic
    role in the gate / Fano line structure; the cube substrate treats
    these names as opaque vertex labels.
    """
    Void    = 0   # 000
    Fire    = 1   # 001
    Earth   = 2   # 010
    Order   = 3   # 011
    Chaos   = 4   # 100
    Air     = 5   # 101
    Water   = 6   # 110
    Aether  = 7   # 111


@dataclass
class ElementCube:
    """One element state over F_2^3: Bott values with per-vertex presence masks.

    Values: float per vertex, range [-1, +1]. Positive = aligned, negative = opposed.
    Present: bool per vertex. False = blind (vertex not visible in this state).
    preset: optional Affinity the state was loaded from (None = custom).
    """
    values: list[float] = field(default_factory=lambda: [0.0] * Bott)
    present: list[bool] = field(default_factory=lambda: [True] * Bott)
    preset: Optional[Affinity] = None

    def __post_init__(self):
        if len(self.values) != Bott:
            raise ValueError(f"values must have {Bott} entries, got {len(self.values)}")
        if len(self.present) != Bott:
            raise ValueError(f"present must have {Bott} entries, got {len(self.present)}")

    @classmethod
    def from_values(cls, values: Sequence[Optional[float]]) -> "ElementCube":
        """Create from explicit values. None entries mark absent vertices."""
        vals = [0.0] * Bott
        pres = [False] * Bott
        for i in range(Bott):
            if i < len(values) and values[i] is not None:
                v = float(values[i])
                vals[i] = max(-1.0, min(1.0, v))
                pres[i] = True
        return cls(values=vals, present=pres)

    def clone(self) -> "ElementCube":
        return ElementCube(values=list(self.values), present=list(self.present), preset=self.preset)

    def load_from_gate_string(self, element: Affinity) -> None:
        """Load the canonical gate-string preset for a pure element.

        Self=1, Ally=0.5, Balanced=0, Friction=-0.5, Opp=-1, Blind=absent.
        """
        from s3.cubes.gate_system import gate_string_to_values
        gate_values = gate_string_to_values(element)
        for i in range(Bott):
            v = gate_values[i]
            if v is None:
                self.values[i] = 0.0
                self.present[i] = False
            else:
                self.values[i] = v
                self.present[i] = True
        self.preset = element

    def get_dominant(self) -> Affinity:
        """Return the vertex with highest absolute value among present ones."""
        best = 0
        best_abs = -1.0
        for i in range(Bott):
            if not self.present[i]:
                continue
            a = abs(self.values[i])
            if a > best_abs:
                best_abs = a
                best = i
        return Affinity(best)

    @property
    def present_count(self) -> int:
        return sum(1 for p in self.present if p)

    @property
    def total_energy(self) -> float:
        return sum(abs(self.values[i]) for i in range(Bott) if self.present[i])

    def reset(self) -> None:
        """Zero all values; keep presence unchanged."""
        self.values = [0.0] * Bott
        self.preset = None

    def __repr__(self) -> str:
        vals = ", ".join(f"{v:+.2f}" if self.present[i] else "  ---" for i, v in enumerate(self.values))
        preset = self.preset.name if self.preset is not None else "custom"
        return f"ElementCube[{preset}]({vals})"
