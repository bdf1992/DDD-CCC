"""
FilesystemCodeAdapter — walks a directory tree, picks common code extensions,
emits canonical SourceRecords.

Siblings the FilesystemMarkdownAdapter. The staleness datums look for
prose<->code edges; a markdown-only candidate pool has no code half of
the edge, which is why the code adapter sits alongside.

For Python files, extracts `import X` / `from X import Y` lines as
outbound_refs so the staleness + cross-reference datums can draw real edges.

Other languages: extension-based collection only; outbound_refs left empty.
Richer per-language reference extraction lives in later plugins.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from s3.cubes.adapters.base import SourceRef, SourceRecord, SourceAdapter


# Common source-code extensions. Extend as needed.
DEFAULT_CODE_EXTENSIONS = (
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".c", ".h", ".cpp", ".hpp",
    ".cs", ".go", ".rs", ".java", ".kt", ".swift",
    ".rb", ".sh", ".bash", ".zsh",
    ".lua", ".pl", ".php", ".sql",
)


# Python import extraction: `import X` / `import X as Y` / `from X import Y`
_PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import\s+|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))",
    re.MULTILINE,
)


class FilesystemCodeAdapter:
    """Walks a directory, emits every recognized code file as a SourceRecord.

    Config:
        root               : directory to walk
        extensions         : tuple of extensions to collect (includes leading dot)
        exclude            : glob patterns under root to skip
        follow_symlinks    : default False
    """
    name = "code"

    def __init__(
        self,
        root: Path | str,
        extensions: tuple[str, ...] = DEFAULT_CODE_EXTENSIONS,
        exclude: tuple[str, ...] = (),
        follow_symlinks: bool = False,
    ):
        self.root = Path(root).resolve()
        self.extensions = tuple(e.lower() for e in extensions)
        self.exclude = tuple(exclude)
        self.follow_symlinks = follow_symlinks

    def _iter_files(self):
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            if not self.follow_symlinks and p.is_symlink():
                continue
            if p.suffix.lower() not in self.extensions:
                continue
            rel = p.relative_to(self.root).as_posix()
            if any(Path(rel).match(pat) for pat in self.exclude):
                continue
            yield p

    def discover(self) -> list[SourceRef]:
        return [SourceRef(adapter=self.name, uri=str(p)) for p in self._iter_files()]

    def read(self, ref: SourceRef) -> SourceRecord:
        path = Path(ref.uri)
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            body = ""
        stat = path.stat()

        # Outbound refs: imports for Python; empty for other languages at v0
        outbound = _extract_outbound_refs(path, body)

        # Title: first docstring / first comment line / basename
        title = _extract_title(path, body) or path.stem

        return SourceRecord(
            source_id=ref.stable_id(),
            source_type="code",
            uri=str(path),
            title=title,
            body=body,
            metadata={
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "path_parts": path.relative_to(self.root).as_posix().split("/"),
                "extension": path.suffix.lower(),
                "language": _extension_to_language(path.suffix.lower()),
            },
            version_hash=SourceRecord.fingerprint(body),
            observed_at=datetime.now(tz=timezone.utc).isoformat(),
            parent_refs=[str(path.parent.resolve())],
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


def _extract_outbound_refs(path: Path, body: str) -> list[str]:
    """Extract outbound references from code. Python imports supported at v0."""
    if path.suffix.lower() != ".py":
        return []
    refs: list[str] = []
    for m in _PY_IMPORT_RE.finditer(body):
        from_mod, import_group = m.group(1), m.group(2)
        if from_mod:
            refs.append(from_mod)
        elif import_group:
            for piece in import_group.split(","):
                piece = piece.strip().split(" as ")[0].strip()
                if piece:
                    refs.append(piece)
    return refs


def _extract_title(path: Path, body: str) -> Optional[str]:
    """First docstring or first comment line."""
    if not body:
        return None
    # Python-style docstring on line 1
    if path.suffix.lower() == ".py":
        stripped = body.lstrip()
        if stripped.startswith(('"""', "'''")):
            quote = stripped[:3]
            end = stripped.find(quote, 3)
            if end > 3:
                doc = stripped[3:end].strip()
                first_line = doc.split("\n", 1)[0].strip()
                if first_line:
                    return first_line[:80]
    # Any-language first comment line starting with //, #, --, /*, or ;
    for line in body.splitlines()[:20]:
        ls = line.strip()
        if not ls:
            continue
        for prefix in ("//", "# ", "-- ", "/* ", "; "):
            if ls.startswith(prefix):
                clean = ls[len(prefix):].strip().rstrip("*/")
                if clean:
                    return clean[:80]
        break
    return None


def _extension_to_language(ext: str) -> str:
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript",
        ".c": "c", ".h": "c", ".cpp": "c++", ".hpp": "c++",
        ".cs": "c#", ".go": "go", ".rs": "rust", ".java": "java",
        ".kt": "kotlin", ".swift": "swift", ".rb": "ruby",
        ".sh": "shell", ".bash": "shell", ".zsh": "shell",
        ".lua": "lua", ".pl": "perl", ".php": "php", ".sql": "sql",
    }.get(ext, "unknown")
