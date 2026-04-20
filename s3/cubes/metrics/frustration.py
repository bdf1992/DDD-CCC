"""
FrustrationMetric — H^0-style incoherence on incident edges + faces.

Surfaces cells where neighbors disagree in a structurally detectable way.
Uses a lightweight proxy signal: an edge is "frustrated" when its two
vertex-endpoints carry concepts of different classified types AND no
higher-rank cell co-places them (i.e., no face or volume brings them
under a shared interpretation). A face is frustrated when ≥ 2 of its 4
bounding edges are frustrated.

This is a sentinel — a fuller sheaf H^0 computation can plug in as a
richer variant later. The proxy here is runnable on any KnowledgeIR
without needing the full sheaf stack.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.metrics.base import MetricResult


class FrustrationMetric:
    name = "frustration"
    fires_at = frozenset({"accept", "modify", "sweep", "ci"})

    def measure(self, ir) -> MetricResult:
        cube = ir.cube
        if cube is None:
            return MetricResult(
                name=self.name,
                scalars={"frustrated_edge_count": 0, "frustrated_face_count": 0},
                summary="no cube attached — frustration undefined",
            )

        by_id = ir.candidates_by_id()
        from s3.cubes.measure import classify_type

        def cell_types(cell_label: str) -> set[str]:
            ids = ir.placements.get(cell_label, [])
            return {classify_type(by_id[i]) for i in ids if i in by_id}

        # Edges: frustrated if two endpoints have disjoint type sets AND no co-face
        # pulls them under a shared type.
        frustrated_edges: list[str] = []
        cell_readings: dict = {}
        for edge in cube.cells_by_rank.get(1, []):
            vs = cube.faces_of.get(edge, frozenset())
            if len(vs) != 2:
                continue
            v_types = [cell_types(v.label) for v in vs]
            if not all(v_types):
                continue  # any endpoint empty -> not frustrated, just vacuous
            a, b = v_types
            if a & b:
                continue  # shared type -> coherent
            # no shared type at the endpoints — check co-faces
            coface_types: set[str] = set()
            for cf in cube.cofaces_of.get(edge, frozenset()):
                coface_types |= cell_types(cf.label)
            if coface_types & (a | b):
                continue  # a higher cell reconciles them
            frustrated_edges.append(edge.label)
            cell_readings[edge.label] = {"rank": 1, "frustrated": True,
                                          "endpoint_types": [sorted(a), sorted(b)]}

        # Faces: frustrated if >= 2 bounding edges are frustrated.
        frustrated_faces: list[str] = []
        fe_set = set(frustrated_edges)
        for face in cube.cells_by_rank.get(2, []):
            bounding = cube.faces_of.get(face, frozenset())
            count = sum(1 for e in bounding if e.label in fe_set)
            if count >= 2:
                frustrated_faces.append(face.label)
                cell_readings[face.label] = {"rank": 2, "frustrated": True,
                                              "frustrated_edge_count": count}

        scalars = {
            "frustrated_edge_count": len(frustrated_edges),
            "frustrated_face_count": len(frustrated_faces),
        }
        summary = (
            f"frustration: {len(frustrated_edges)} edges, "
            f"{len(frustrated_faces)} faces with unreconciled type disagreement"
        )
        return MetricResult(
            name=self.name,
            scalars=scalars,
            cell_readings=cell_readings,
            summary=summary,
        )
