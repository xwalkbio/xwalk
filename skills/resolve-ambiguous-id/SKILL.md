---
name: resolve-ambiguous-id
description: Turn a messy protein identifier into one pinned, citable ID. Handles bare gene names or synonyms across species ("p53"), gene_SPECIES names ("TP53_HUMAN"), accessions with many isoforms, multi-chain PDB entries with no chain given, AlphaFold IDs and raw sequences. Asks at most one clarifying question. Use when the user names a protein loosely, or when an ID must be pinned before it is cited, compared or passed to another tool.
---

# Resolve an ambiguous identifier

`resolve_target` does the walking across UniProt, PDB and AlphaFold DB. Your job is to
pass the input through unchanged, ask at most one question when it says `ambiguous`,
and report the pinned ID.

## Steps

1. Call `resolve_target(q=<the input exactly as given>)`. Add `organism` only if the user
   already said the species ("human p53" → `organism=9606`). Don't clean up, translate or
   guess the input first. The service reads gene names, synonyms, accessions, entry names,
   `GENE_SPECIES`, PDB entries and chains (`5JXE`, `5JXE_A`, `5JXE.A`), AF IDs, `seq:`/`str:` IDs
   and raw sequences.
2. Act on `status`:
   - `resolved`: done. The pinned ID is `seq_id`. Mention `isoforms` if there are any (a bare
     accession means the canonical isoform; another isoform needs its suffix, e.g. `P04637-2`).
   - `ambiguous`: ask the user **one** question built from `disambiguate_by` and `candidates`
     (at most 10, each carrying the field that separates them), then call `resolve_target`
     again with the answer: `organism=<taxid>` for organism, `q="<entry>_<auth chain>"` for
     chain, `q=<accession>` for accession. Don't ask a second question. If the answer still
     doesn't resolve, report the candidates and stop.
   - `not_found`: report the `hint`. For a raw sequence, a `seq_id` is still returned (a
     content hash), so the sequence can be cited even though it is not indexed.
   - `error`: follow `error.hint` once (for example, fix the parameter), otherwise report it.
3. If the user needs a structure, not just the target (for example a specific chain of a
   PDB entry they named), call `get_structure(id=<seq_id or str: ID>)`. It returns the pinned
   `str:` ID with its chains.
4. Report the pinned ID and how it was reached (for example "p53, human → P04637 →
   seq:sha256:…"). Cite IDs exactly as returned.

## Worked examples

- **"p53"** → `ambiguous`, `disambiguate_by: "organism"`, with human, mouse and rat first
  among the candidates (`candidates_total` counts them all; at most 10 are listed). Ask "Which species?",
  naming human (9606), mouse (10090) and rat (10116) and offering to take any NCBI taxid → `resolve_target(q="p53", organism=9606)`
  → `resolved`, P04637. A species not in the listed 10 still works: pass its taxid.
- **"TP53_HUMAN"** → `resolved`, P04637. This is gene plus species mnemonic; the real
  entry name is P53_HUMAN, and both work.
- **"P04637"** → `resolved` to the canonical isoform, with 8 other isoforms listed under
  `isoforms`. No question needed.
- **"5JXE"** → `ambiguous`, `disambiguate_by: "chain"`: the entry has several distinct
  chain sequences, among them chains A and B mapped to Q15116 (PD-1). Ask which chain, then
  `resolve_target(q="5JXE_A")` → `resolved`, with Q15116 under `mapped_uniprot` (the construct
  is not identical to the UniProt sequence, so it maps rather than matches).
- **A raw CDK2 sequence** → `resolved`, P24941 (exact sequence match).

## Don't do this

- Don't ask a clarifying question before calling the tool. Most inputs resolve directly.
- Don't pick a candidate yourself when the result is `ambiguous` (for example, assuming
  human). Ask once.
- Don't merge or equate entries by similarity. A variant, isoform or fragment is a different
  `seq:` ID by design, and an ortholog is a different target.
- Don't rewrite the user's input (uppercasing, removing the chain, trimming a sequence)
  before sending it. The service normalizes it, and the response echoes what it matched.
- Don't cite a PDB code, accession or versionless `str:` ID as the result. Cite the pinned
  `seq:` or `str:` ID the tool returned.
