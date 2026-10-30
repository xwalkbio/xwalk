# Recorded session: "Set up human CDK2 for docking."

Claude Code 2.1, the `xwalk` plugin, and the hosted service on Google Cloud, recorded Oct 30, 2026 in a non-interactive run. Abridged: long tool results are cut to the fields the skill uses, four checks Claude ran on the output file are omitted, and the working-directory path is shortened. Tool inputs and the final answer are otherwise verbatim.

**User:** Set up human CDK2 for docking.

**Claude:** I'll use the docking target preparation skill for human CDK2.

*The `prepare-docking-target` skill loads.*

**Tool call: resolve_target**
```json
{
  "q": "CDK2",
  "organism": 9606
}
```

**Result (abridged):**
```json
{
  "status": "resolved",
  "seq_id": "seq:sha256:fe22d91e18cd544a85d7c768cd864172200252df906b774d890dc103224f7c8d",
  "sequence_length": 298,
  "uniprot": [
    {
      "accession": "P24941",
      "entry_name": "CDK2_HUMAN",
      "is_canonical": true,
      "isoform_id": "P24941-1",
      "sequence_version": 2,
      "taxid": 9606,
      "organism": "Homo sapiens (Human)",
      "gene": "CDK2"
    }
  ],
  "structures": "[25 candidates, tiered against the full length]"
}
```

**Tool call: get_structure**
```json
{
  "id": "seq:sha256:fe22d91e18cd544a85d7c768cd864172200252df906b774d890dc103224f7c8d",
  "region": "Protein kinase",
  "want": "docking"
}
```

**Result (abridged):**
```json
{
  "status": "resolved",
  "id": "str:pdb:11GV@1.0",
  "method": "X-RAY DIFFRACTION",
  "resolution": 1.59,
  "tier": "A",
  "reason": "tier A: 1.59 Å X-ray, 100% coverage, no unresolved gaps",
  "ligand_bound": true,
  "ligands": [
    "A1DEQ",
    "CL",
    "DMS",
    "EDO",
    "IPA",
    "MG"
  ],
  "file_url": "https://files-versioned.wwpdb.org/pdb_versioned/data/entries/1g/pdb_000011gv/pdb_000011gv_xyz_v1-0.cif.gz",
  "tiers": {
    "target": "P24941",
    "region": [
      4,
      286
    ],
    "region_name": "Protein kinase",
    "want": "docking",
    "rules": {
      "version": "1.0",
      "a_max_resolution": 2.5,
      "b_max_resolution": 3.5,
      "min_coverage": 0.8,
      "b_min_mean_plddt": 85,
      "b_min_roi_plddt": 70,
      "low_plddt_stretch": 5
    }
  },
  "chains": [
    {
      "label_asym_id": "A",
      "auth_asym_id": "A",
      "uniprot_accessions": [
        "P24941"
      ]
    },
    {
      "label_asym_id": "B",
      "auth_asym_id": "B",
      "uniprot_accessions": [
        "P20248"
      ]
    }
  ]
}
```

**Tool call: Bash**
```
uv run ${CLAUDE_PLUGIN_ROOT}/skills/prepare-docking-target/scripts/prepare_target.py --id str:pdb:11GV@1.0 --file-url https://files-versioned.wwpdb.org/pdb_versioned/data/entries/1g/pdb_000011gv/pdb_000011gv_xyz_v1-0.cif.gz --chains A --out cdk2_receptor.pdb
```

**Result:**
```json
{
  "id": "str:pdb:11GV@1.0",
  "chain": "A",
  "ligand": {
    "comp_id": "A1DEQ",
    "auth_chain": "A",
    "auth_seq_id": 317,
    "heavy_atoms": 28,
    "contacts": 28
  },
  "pocket": {
    "center": [
      -17.128,
      -25.895,
      22.614
    ],
    "source": "bound ligand centroid"
  },
  "receptor": "cdk2_receptor.pdb",
  "residues": 290
}
```

*Between the calls Claude noted:* "Resolved to human CDK2 (P24941). Now picking the best kinase-domain structure for docking." / "Chain A maps to CDK2 (chain B is cyclin A2). Running the receptor preparation script."

**Claude:** Human CDK2 is set up for docking. The receptor file and pocket center are ready.

**Receptor:** `cdk2_receptor.pdb`

**Structure used:** str:pdb:11GV@1.0, chain A. Cite this pinned ID verbatim, since it reproduces the exact same structure later. It was ranked tier A by the selection tool: 1.59 Å X-ray, 100% coverage of the kinase domain (UniProt P24941 residues 4 to 286), no unresolved gaps, ligand-bound.

**Pocket center:** (-17.13, -25.90, 22.61) Å. This is the heavy-atom centroid of the co-crystallized inhibitor A1DEQ in chain A. All 28 of its heavy atoms are in contact with the receptor chain, so the box sits on the ATP site.

Things to know about the prepared file:

- **Cyclin removed.** The entry is a CDK2 and cyclin A2 complex. Only the CDK2 chain was kept, so the receptor is in its active, cyclin-bound conformation with the cyclin interface now exposed. Poses near the C-helix or that face should be read with that in mind.
- **Phospho-Thr160 kept.** Residue 160 is phosphothreonine (TPO) and is written as HETATM lines. It is part of the chain, so it was left in. If your docking tool rejects it, convert it during that tool's receptor preparation rather than deleting it from this file.
- **Everything else stripped.** Waters, the inhibitor, and the buffers and ions in the entry (chloride, DMSO, ethylene glycol, isopropanol, magnesium) were all removed.

Box size and other docking parameters are not set, since those depend on the docking program you choose.
