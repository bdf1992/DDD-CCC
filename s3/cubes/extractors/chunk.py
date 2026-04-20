"""
Chunking — split large bodies into placement-unit-sized pieces.

Simple strategy: split by blank-line-delimited paragraphs, then
merge small paragraphs until each chunk crosses a minimum length. Headings
anchor chunk boundaries.

Richer strategies (AST-aware for code, heading-hierarchy for markdown,
semantic embedding-based) can plug in later via additional chunker variants.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)


@dataclass
class Chunk:
    """One placement-unit-sized chunk of a source body.

    parent_source_id : the SourceRecord.source_id this chunk came from
    index            : 0-based chunk index within the source
    heading          : the nearest preceding heading (or None)
    body             : the chunk text
    offset           : (start, end) character offsets in the parent body
    """
    parent_source_id: str
    index: int
    heading: str | None
    body: str
    offset: tuple[int, int]


def chunk_body(
    source_id: str,
    body: str,
    min_chars: int = 200,
    max_chars: int = 2000,
) -> list[Chunk]:
    """Split a body into Chunks. Heading-aware.

    If the body has headings, each chunk is anchored to its nearest preceding
    heading. Consecutive paragraphs are merged until the merged chunk meets
    `min_chars`. A chunk never exceeds `max_chars` (split at paragraph
    boundaries; final fallback splits at sentence boundaries).
    """
    if not body.strip():
        return []

    # Walk the body paragraph-by-paragraph with character offsets.
    paragraphs = _paragraphs_with_offsets(body)
    if not paragraphs:
        return []

    # Anchor each paragraph to its nearest preceding heading.
    heading_positions = [(m.start(), body[m.start():body.index("\n", m.start()) if "\n" in body[m.start():] else len(body)].strip())
                         for m in _HEADING_RE.finditer(body)]

    def heading_for_offset(off: int) -> str | None:
        last: str | None = None
        for h_off, h_text in heading_positions:
            if h_off <= off:
                last = h_text
            else:
                break
        return last

    chunks: list[Chunk] = []
    buf_text_parts: list[str] = []
    buf_start: int = -1
    buf_end: int = -1
    idx = 0

    def flush():
        nonlocal buf_text_parts, buf_start, buf_end, idx
        if not buf_text_parts:
            return
        chunk_text = "\n\n".join(buf_text_parts).strip()
        if chunk_text:
            chunks.append(Chunk(
                parent_source_id=source_id,
                index=idx,
                heading=heading_for_offset(buf_start),
                body=chunk_text,
                offset=(buf_start, buf_end),
            ))
            idx += 1
        buf_text_parts = []
        buf_start = -1
        buf_end = -1

    for (pstart, pend, ptext) in paragraphs:
        # Single paragraph already too large: split it.
        if len(ptext) > max_chars:
            flush()
            for (ss, se, st) in _split_large_paragraph(ptext, pstart, max_chars):
                chunks.append(Chunk(
                    parent_source_id=source_id,
                    index=idx,
                    heading=heading_for_offset(ss),
                    body=st,
                    offset=(ss, se),
                ))
                idx += 1
            continue

        if buf_start < 0:
            buf_start = pstart
        buf_end = pend
        buf_text_parts.append(ptext)

        if sum(len(p) for p in buf_text_parts) >= min_chars:
            flush()

    flush()
    return chunks


def _paragraphs_with_offsets(body: str) -> list[tuple[int, int, str]]:
    """Split body by blank lines. Return [(start_offset, end_offset, text), ...]."""
    out: list[tuple[int, int, str]] = []
    i = 0
    n = len(body)
    while i < n:
        while i < n and body[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        while i < n:
            if body[i] == "\n":
                # blank-line boundary: a newline followed by (optional whitespace + newline)
                j = i + 1
                while j < n and body[j] in " \t":
                    j += 1
                if j < n and body[j] == "\n":
                    break
                if j >= n:
                    break
            i += 1
        end = i
        text = body[start:end].strip()
        if text:
            out.append((start, end, text))
        i = end + 1
    return out


def _split_large_paragraph(text: str, base_offset: int, max_chars: int) -> list[tuple[int, int, str]]:
    """Fallback splitter for very long paragraphs: split at sentence-ish boundaries."""
    out: list[tuple[int, int, str]] = []
    buf = ""
    buf_start = base_offset
    pos = base_offset
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        if not s:
            continue
        if len(buf) + len(s) + 1 > max_chars and buf:
            out.append((buf_start, pos, buf.strip()))
            buf = s
            buf_start = pos
        else:
            if buf:
                buf += " " + s
            else:
                buf = s
                buf_start = pos
        pos += len(s) + 1
    if buf.strip():
        out.append((buf_start, pos, buf.strip()))
    return out
