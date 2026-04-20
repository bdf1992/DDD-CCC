"""
FilesystemMarkdownAdapter — walks a directory tree, yields every .md file
as a canonical SourceRecord.

The fallback adapter: works on any repo with markdown in it. No frontmatter
parsing here (plain .md). Obsidian-specific features (wikilinks, dataview) live
in ObsidianVaultAdapter.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRef, SourceRecord, SourceAdapter


_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
# Match any `[text](target)` where target is a relative path (not http/https/mailto
# and not a pure anchor). Extracts .md, .py, .ts, .json, path/to/file, etc.
_REL_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


class FilesystemMarkdownAdapter:
    """Walks a root directory, yields every `*.md` file as a SourceRecord.

    Config:
        root        : directory to walk (Path or str).
        exclude     : iterable of glob patterns to skip (e.g. ["node_modules/**"]).
        follow_symlinks : bool, default False.
    """
    name = "markdown"

    def __init__(
        self,
        root: Path | str,
        exclude: tuple[str, ...] = (),
        follow_symlinks: bool = False,
    ):
        self.root = Path(root).resolve()
        self.exclude = tuple(exclude)
        self.follow_symlinks = follow_symlinks

    def _iter_files(self):
        for p in self.root.rglob("*.md"):
            if not self.follow_symlinks and p.is_symlink():
                continue
            rel = p.relative_to(self.root).as_posix()
            if any(Path(rel).match(pat) for pat in self.exclude):
                continue
            yield p

    def discover(self) -> list[SourceRef]:
        return [SourceRef(adapter=self.name, uri=str(p)) for p in self._iter_files()]

    def read(self, ref: SourceRef) -> SourceRecord:
        path = Path(ref.uri)
        body = path.read_text(encoding="utf-8", errors="replace")
        stat = path.stat()
        title = _extract_title(body) or path.stem
        outbound = _extract_relative_links(body)
        parent = str(path.parent.resolve())

        return SourceRecord(
            source_id=ref.stable_id(),
            source_type="markdown",
            uri=str(path),
            title=title,
            body=body,
            metadata={
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "path_parts": path.relative_to(self.root).as_posix().split("/"),
                "extension": ".md",
            },
            version_hash=SourceRecord.fingerprint(body),
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            parent_refs=[parent],
            outbound_refs=outbound,
        )

    def changed_since(self, watermark: Optional[str]) -> list[SourceRef]:
        if watermark is None:
            return self.discover()
        try:
            wm = datetime.fromisoformat(watermark)
        except ValueError:
            return self.discover()
        out: list[SourceRef] = []
        for p in self._iter_files():
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if mtime > wm:
                out.append(SourceRef(adapter=self.name, uri=str(p)))
        return out


def _extract_title(body: str) -> Optional[str]:
    """First H1 heading, else None."""
    m = _HEADING_RE.search(body)
    return m.group(1).strip() if m else None


def _extract_relative_links(body: str) -> list[str]:
    """Markdown `[text](target)` relative path links. Excludes http(s)/mailto/anchors/absolute."""
    out: list[str] = []
    for m in _REL_LINK_RE.finditer(body):
        target = m.group(1).split("#", 1)[0].strip()
        if not target:
            continue
        if target.startswith(("http://", "https://", "mailto:", "/", "#", "javascript:")):
            continue
        # Must look path-like: contain a "/" or "." (extension or relative ref)
        if "/" not in target and "." not in target:
            continue
        out.append(target)
    return out
