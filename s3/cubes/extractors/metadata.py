"""
Metadata normalization — consolidate adapter-specific metadata into a small
canonical schema the placement engine + datums can read uniformly.

Canonical fields:
    modified_at   : ISO 8601 timestamp of last modification (from source system)
    size_bytes    : integer byte size (or len(body))
    tags          : list[str] of normalized tags
    path_parts    : list[str] path segments from repo root (if applicable)
    extension     : file extension, including the dot
    primitive     : for Greenfield rows, the primitive kind ("source" / "datapoint" / ...)

Original adapter metadata is preserved under the `_raw` key.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRecord


CANONICAL_FIELDS = (
    "modified_at", "size_bytes", "tags", "path_parts", "extension", "primitive",
)


def normalize_metadata(record: SourceRecord) -> dict:
    """Produce a canonical metadata dict from a SourceRecord.

    Leaves the original SourceRecord untouched; callers may attach the result
    under `record.metadata["_canonical"]` or use it inline.
    """
    md = record.metadata or {}
    out: dict = {}

    # modified_at
    out["modified_at"] = _first_present(md, "modified_at") or record.observed_at

    # size_bytes
    size = _first_present(md, "size_bytes")
    out["size_bytes"] = int(size) if isinstance(size, (int, float, str)) and str(size).strip().isdigit() \
                       else len(record.body.encode("utf-8"))

    # tags
    tags = md.get("tags")
    if isinstance(tags, list):
        out["tags"] = [str(t) for t in tags]
    elif isinstance(tags, str):
        out["tags"] = [s.strip() for s in tags.split(",") if s.strip()]
    else:
        fm = md.get("frontmatter") or {}
        fm_tags = fm.get("tags") if isinstance(fm, dict) else None
        if isinstance(fm_tags, list):
            out["tags"] = [str(t) for t in fm_tags]
        elif isinstance(fm_tags, str):
            out["tags"] = [s.strip() for s in fm_tags.split(",") if s.strip()]
        else:
            out["tags"] = []

    # path_parts
    pp = _first_present(md, "path_parts")
    if isinstance(pp, list):
        out["path_parts"] = [str(x) for x in pp]
    else:
        vp = _first_present(md, "vault_path")
        out["path_parts"] = vp.split("/") if isinstance(vp, str) else []

    # extension
    ext = _first_present(md, "extension")
    out["extension"] = str(ext) if isinstance(ext, str) else ""

    # primitive (Greenfield-specific)
    prim = _first_present(md, "primitive")
    out["primitive"] = str(prim) if isinstance(prim, str) else ""

    out["_raw"] = md
    return out


def _first_present(d: dict, key: str) -> Optional[object]:
    v = d.get(key)
    if v is None or v == "":
        return None
    return v
