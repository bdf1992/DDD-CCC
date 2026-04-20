---
title: Fixture README
tags: [fixture]
---

# obsidian_vault_mini

Minimal Obsidian vault used by the `adapter-design` skill-vs-code test for
`ObsidianVaultAdapter`.

**Shape**: three concept notes (`index`, `signal`, `entropy`) with wikilinks
between them plus three intentionally-unresolved targets:

- `MISSING_GLOSSARY` (from index)
- `MISSING_CHANNEL` (from signal)
- `wikipedia-external` (from entropy — whitelist candidate in corrective proof)

The unresolved set is the witness for the adapter's pressure claim and drives
the `unresolved_wikilink_term` datum runner. The corrective proof whitelists
`wikipedia-external`; before/after datum counts must differ.

Keep this fixture small. Adding notes or links here changes the proof
expected counts — update the test module alongside.
