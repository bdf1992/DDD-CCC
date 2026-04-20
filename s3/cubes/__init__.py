"""
s3.cubes — Coverage Cube substrate:
3-cube combinatorial complex (ranks 0/1/2/3), element cube primitives,
measurement operators, and the ETL spine for semantic coverage.

Entry points:
    ElementCube         — 8-value F_2^3 primitive
    element_algebra     — popcount, hamming, V_4 axis projection, HdMatch, meta spectrum
    gate_system         — 7 Fano lines, 8x8 GateType table, ease + sign, classification
    CubeComplex         — 3-cube combinatorial complex: 0-cells (vertices), 1-cells
                          (edges), 2-cells (faces), 3-cell (volume), with incidence
                          + coface maps, distinction operator, and the identity +
                          axis-against carrier API

Philosophy: the cube is substrate, not content. Users declare axes; this library
provides load / read / metric / traversal primitives. Cell-rank maps onto
test-pyramid scale (vertex=unit, edge=integration, face=interface, volume=e2e).
Reuses `Cell` from `s3/combinatorial_complex.py` and extends its Fano-plane
(ranks 0/1) instance with the full cube ranks 0/1/2/3.
"""

from s3.cubes.element_cube import ElementCube, Affinity
from s3.cubes.element_algebra import (
    popcount, hamming_distance,
    HdMatch, get_hd_match, get_scalar_multiplier, get_additive_score,
    AxisLayer, Axis,
    get_layer, get_axis_profile,
    get_axis_gaps, get_canonical_gap_signature,
    compute_meta_spectrum,
    get_opposition, are_opposed,
    is_lower, is_upper,
)
from s3.cubes.gate_system import (
    GateType, GateSign,
    FANO_LINES,
    build_gate_table, get_gate, get_gate_string, gate_string_to_values,
    ease, sign_preference, resolve_delta, residual,
    share_fano_line, get_fano_lines_of,
)
from s3.cubes.combinatorial_complex import (
    CubeComplex, build_cube_cc,
    cube_vertices, cube_edges, cube_faces, cube_volume,
    distinction_D, axis_against, incidence_neighbors, opposites,
)

# Orientation-orbit sweep.
from s3.cubes.sweep import (
    OrientationElement, cube_orientation_group,
    apply_orientation_to_vector,
    PlacementSignal, compute_signal,
    OrbitReport, orbit_sweep, render_orbit_report,
    IDENTITY, orientation_preserves_hamming,
)

# KnowledgeIR + metrics + profile + placement.
from s3.cubes.ir import KnowledgeIR, KnowledgeIRSnapshot, empty_ir
from s3.cubes.metrics import (
    MetricPlugin, MetricResult, MetricRegistry,
    CoverageMetric, VacuumMetric, FrustrationMetric, RichnessMetric,
)
from s3.cubes.profile import (
    ProfileCard, assemble_profile_card,
    InvariantError, validate_axis_proposal, UNIVERSAL_INVARIANTS,
    AxisProposal, propose_axes,
    AxisConvention, commit_convention,
)
from s3.cubes.placement import (
    PlacementCandidate, PlacementSuggestion, suggest_placements,
    PlacementDecision, DecisionKind, apply_decision,
    SignedDatapoint, emit_datapoint, write_jsonl_stream,
)

# Ports-and-adapters spine.
from s3.cubes.adapters import (
    SourceRef, SourceRecord, SourceAdapter,
    FilesystemMarkdownAdapter, ObsidianVaultAdapter, GreenfieldJsonlAdapter,
)
from s3.cubes.stores import CandidateStore, SearchHit, InMemoryStore
from s3.cubes.extractors import chunk_body, Chunk, normalize_links, normalize_metadata
from s3.cubes.measure import BaseMeasurement, measure, intrinsic, relational, predictive, classify_type
from s3.cubes.datums import (
    Datum, DatumTier, DatumFamily,
    DatumContext, DatumInstance,
    DatumRegistry, ValidationError, validate_datum,
    load_datum_from_dict, load_datum_from_file,
    datum_to_dict, datum_to_yaml,
    standard_declarative_composer,
)

__all__ = [
    # element cube
    "ElementCube", "Affinity",
    # element algebra
    "popcount", "hamming_distance",
    "HdMatch", "get_hd_match", "get_scalar_multiplier", "get_additive_score",
    "AxisLayer", "Axis",
    "get_layer", "get_axis_profile",
    "get_axis_gaps", "get_canonical_gap_signature",
    "compute_meta_spectrum",
    "get_opposition", "are_opposed",
    "is_lower", "is_upper",
    # gate system
    "GateType", "GateSign",
    "FANO_LINES",
    "build_gate_table", "get_gate", "get_gate_string", "gate_string_to_values",
    "ease", "sign_preference", "resolve_delta", "residual",
    "share_fano_line", "get_fano_lines_of",
    # cube combinatorial complex
    "CubeComplex", "build_cube_cc",
    "cube_vertices", "cube_edges", "cube_faces", "cube_volume",
    "distinction_D", "axis_against", "incidence_neighbors", "opposites",
    # adapters
    "SourceRef", "SourceRecord", "SourceAdapter",
    "FilesystemMarkdownAdapter", "ObsidianVaultAdapter", "GreenfieldJsonlAdapter",
    # stores
    "CandidateStore", "SearchHit", "InMemoryStore",
    # extractors
    "chunk_body", "Chunk", "normalize_links", "normalize_metadata",
    # measure
    "BaseMeasurement", "measure", "intrinsic", "relational", "predictive", "classify_type",
    # datums foundation
    "Datum", "DatumTier", "DatumFamily",
    "DatumContext", "DatumInstance",
    "DatumRegistry", "ValidationError", "validate_datum",
    # datum authoring
    "load_datum_from_dict", "load_datum_from_file",
    "datum_to_dict", "datum_to_yaml",
    "standard_declarative_composer",
    # orientation-orbit sweep
    "OrientationElement", "cube_orientation_group",
    "apply_orientation_to_vector",
    "PlacementSignal", "compute_signal",
    "OrbitReport", "orbit_sweep", "render_orbit_report",
    "IDENTITY", "orientation_preserves_hamming",
    # KnowledgeIR
    "KnowledgeIR", "KnowledgeIRSnapshot", "empty_ir",
    # metrics
    "MetricPlugin", "MetricResult", "MetricRegistry",
    "CoverageMetric", "VacuumMetric", "FrustrationMetric", "RichnessMetric",
    # profile
    "ProfileCard", "assemble_profile_card",
    "InvariantError", "validate_axis_proposal", "UNIVERSAL_INVARIANTS",
    "AxisProposal", "propose_axes",
    "AxisConvention", "commit_convention",
    # placement
    "PlacementCandidate", "PlacementSuggestion", "suggest_placements",
    "PlacementDecision", "DecisionKind", "apply_decision",
    "SignedDatapoint", "emit_datapoint", "write_jsonl_stream",
]
