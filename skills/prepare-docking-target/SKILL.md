---
name: prepare-docking-target
description: Prepare a protein receptor for docking from a gene name, UniProt accession or PDB ID. Picks the best experimental structure (tier A, ligand-bound first) for the binding domain, strips waters and hetero groups, keeps the target chain, and returns the pocket center from the bound ligand plus a pinned structure ID to cite. Use when the user wants to dock, run virtual screening, or set up a docking box for a protein target.
---

# Prepare a docking target

Chain two tools, then run one script. Every structure decision comes from the tools; do
not choose or rank structures yourself.

## Steps

1. **Identify the target.** Call `resolve_target(q=<what the user gave>, organism=<taxid if known>)`.
   - `resolved`: keep `seq_id` and the canonical UniProt `accession` (the `uniprot` row with `is_canonical: true`).
   - `ambiguous`: ask the user one question built from `disambiguate_by` and the candidates (for `organism`, list the species), then call again with their answer. Never pick a candidate yourself.
   - `not_found`: report the `hint` and stop.
2. **Pick the structure.** Call `get_structure(id=<seq_id>, region=<binding domain>, want="docking")`.
   - Kinases: `region="Protein kinase"`. For JAK-family kinases with two kinase domains, `"Protein kinase 2"` is the catalytic JH1 domain (`"Protein kinase 1"` is the pseudokinase).
   - GPCRs and other membrane receptors: `region="transmembrane"`.
   - Anything else: omit `region` (full length), or pass the domain name. If you pass a name that does not exist, the error lists the target's region names; retry with one of them.
3. **Prepare the receptor.** From the `get_structure` response, take `id`, `file_url` and the `auth_asym_id` of every chain whose `uniprot_accessions` contains the target accession (for an AlphaFold model, `A`). Then run:

   ```
   uv run ${CLAUDE_PLUGIN_ROOT}/skills/prepare-docking-target/scripts/prepare_target.py \
       --id <id> --file-url <file_url> --chains <A,B> --out <target>_receptor.pdb
   ```

   (Claude Code fills in the plugin path above. If your client left a `${...}` placeholder in it,
   run `scripts/prepare_target.py` from the folder that holds this SKILL.md instead.)

   It downloads the structure from its upstream host, keeps the one target chain in contact with the best bound ligand, removes waters and every non-polymer group, and prints JSON with `chain`, `ligand`, `pocket.center` (Å, the ligand's heavy-atom centroid) and `receptor`.
4. **Report** the pinned `id` (cite it; it reproduces this exact structure), `tier` and `reason`, the chain, the ligand it was bound to, the pocket center and the receptor file path. Say the pocket comes from the co-crystallized ligand. If `get_structure` returned a `hint` (it does when the best pick for docking is tier C), state the hint before the result so the user knows no tier A or B structure covers the region.

## Worked example

User: "Set up CDK2 for docking."

1. `resolve_target(q="CDK2", organism=9606)` → `resolved`, accession `P24941`, `seq_id` `seq:sha256:fe22d91e…`.
2. `get_structure(id="seq:sha256:fe22d91e…", region="Protein kinase", want="docking")` → `str:pdb:11GV@1.0`, tier A, `ligand_bound: true`, chain `A` maps to `P24941`.
3. `uv run …/prepare_target.py --id str:pdb:11GV@1.0 --file-url https://files-versioned.wwpdb.org/pdb_versioned/data/entries/1g/pdb_000011gv/pdb_000011gv_xyz_v1-0.cif.gz --chains A --out cdk2_receptor.pdb`
   → chain `A`, ligand `A1DEQ`, pocket center `[-17.128, -25.895, 22.614]`.
4. "Receptor: CDK2 chain A from str:pdb:11GV@1.0 (tier A: 1.59 Å X-ray, 100% coverage of the kinase domain, no unresolved gaps), waters and ligands removed, saved to cdk2_receptor.pdb. Pocket center (-17.13, -25.90, 22.61) Å, the centroid of the bound inhibitor A1DEQ. Cite str:pdb:11GV@1.0."

## When there is no bound ligand

If the script returns `"pocket": null`, the chosen structure has no ligand in contact
with the target chain (common for apo GPCRs). There is no pocket detection in v1. Tell the
user, show the `hint`, and ask whether they have a site (residues or coordinates) to use.

## Don't do this

- Don't pick a structure from `resolve_target`'s `structures` list. Those tiers are against the full length; only `get_structure` with `region` and `want` ranks for the binding domain.
- Don't invent or look up a pocket center when `pocket` is null, and don't place the box on a buffer or ion. The script already ignores glycerol, sulfate, DMSO, metal ions and similar.
- Don't strip modified residues (phospho-Tyr `PTR`, phospho-Thr `TPO`, `MSE`) from the receptor. They are part of the chain and the script keeps them. If the docking tool rejects them, convert them in that tool's preparation step.
- Don't cite a versionless ID (`str:pdb:11GV`) or a bare PDB code. Cite the pinned `id` exactly as returned.
- Don't fall back to an AlphaFold model for docking because it is full length when `get_structure` returned an experimental tier A or B structure. The selection order already weighs that.
- Don't guess the organism. If `resolve_target` is ambiguous by organism, ask.
