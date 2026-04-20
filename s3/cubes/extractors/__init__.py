"""
s3.cubes.extractors — post-adapter preparation layer.

Adapters produce SourceRecords. Extractors prepare those records for the
placement engine: chunking large bodies, normalizing links, canonicalizing
metadata. Extractors do not write to the cube; they refine the candidate.
"""

from s3.cubes.extractors.chunk import chunk_body, Chunk
from s3.cubes.extractors.links import normalize_links
from s3.cubes.extractors.metadata import normalize_metadata

__all__ = [
    "chunk_body", "Chunk",
    "normalize_links",
    "normalize_metadata",
]
