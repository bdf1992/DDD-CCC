"""
s3.cubes.adapters — Source adapters for the Coverage Cube.

A source adapter answers: "How do I read this project's knowledge?"
Every adapter emits the same canonical shape: SourceRecord.

Markdown is not special. Obsidian is not special. JIRA is not special.
They are all just ways to produce SourceRecord instances that enter the
store → placement engine → signed-datapoint pipeline.

Invariant: a source adapter NEVER writes directly to the cube.
The only path is Adapter -> CandidateStore -> PlacementEngine -> Decision -> Datapoint.
"""

from s3.cubes.adapters.base import (
    SourceRef,
    SourceRecord,
    SourceAdapter,
)
from s3.cubes.adapters.filesystem_markdown import FilesystemMarkdownAdapter
from s3.cubes.adapters.obsidian_vault import ObsidianVaultAdapter
from s3.cubes.adapters.greenfield_jsonl import GreenfieldJsonlAdapter
from s3.cubes.adapters.filesystem_code import FilesystemCodeAdapter

__all__ = [
    "SourceRef", "SourceRecord", "SourceAdapter",
    "FilesystemMarkdownAdapter",
    "ObsidianVaultAdapter",
    "GreenfieldJsonlAdapter",
    "FilesystemCodeAdapter",
]
