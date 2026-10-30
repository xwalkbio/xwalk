<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License"></a>
  <a href="https://agent-plugins.org"><img src="https://img.shields.io/badge/Agent%20Plugins-1.0-green" alt="Agent Plugins 1.0"></a>
</p>

Xwalk resolves any protein identifier (gene name, UniProt accession, PDB entry or chain, AlphaFold ID, raw sequence) to one pinned, quality-tiered structure with a stable ID, cross-references to AlphaFold DB, PDB, UniProt/UniParc and ESM Atlas, and full provenance.

It is delivered agent-first: a hosted MCP server, plus the two skills in this repository, with a REST API underneath. This repository holds the plugin. The hosted service's public API is documented here until it has its own docs site. There is nothing to build or install from source.

**Status: early access.** The hosted service is at `mcp.xwalk.bio` (MCP) and `api.xwalk.bio` (REST); the plugin's default MCP URL points there.

## What v1 provides

- **Resolve** gene names, UniProt accessions, PDB entries/chains, AlphaFold IDs or raw sequences to pinned IDs in one call.
- **Pinned IDs** at three levels: sequence (`seq:sha256:…`), structure (`str:<source>:<native>@<version>`), and derived object (`obj:…`).
- **Quality tiers** (A/B/C) on every structure, each with a reason string, so callers never interpret pLDDT or resolution themselves.
- **Provenance** on every response: crosswalk snapshot, upstream release versions, licenses and attribution. The same input against the same snapshot returns the same bytes.
- **Three MCP tools** (`resolve_target`, `get_structure`, `get_annotations`), each mapped 1:1 to a REST endpoint (`/v1/resolve`, `/v1/structure/{id}`, `/v1/annotations/{id}`).
- **Two skills:** `prepare-docking-target` and `resolve-ambiguous-id`.

Every call needs an API key issued to your organization, sent as `Authorization: Bearer <key>`. Write to hello@xwalk.bio for one.

## Install the plugin

**Claude Code:**

```
/plugin install xwalk --marketplace xwalkbio/xwalk
```

Claude Code asks for your API key when the plugin is enabled and keeps it in the system keychain. The MCP server URL has a default; change it only if you were given another.

**Codex, Cursor, GitHub Copilot, VS Code and other [Agent Plugins](https://agent-plugins.org) clients:** install from this repository with your client's plugin command. Agent Plugins 1.0 has no way for a plugin to carry a credential, so add the header `Authorization: Bearer <key>` to the `xwalk` MCP server in your client's own MCP settings.

The docking skill's script runs on your machine with `uv run skills/prepare-docking-target/scripts/prepare_target.py` (it declares its own dependency, gemmi, inline).

## In Claude Code

"Set up CDK2 for docking", with the plugin installed. A recorded session against the hosted service is in [`examples/cdk2-transcript.md`](examples/cdk2-transcript.md). In brief:

1. The `prepare-docking-target` skill loads.
2. `resolve_target(q="CDK2", organism=9606)` returns `resolved`, P24941.
3. `get_structure(id=<seq_id>, region="Protein kinase", want="docking")` returns `str:pdb:11GV@1.0`, tier A (1.59 Å X-ray, 100% coverage of the kinase domain), ligand-bound.
4. The skill's script fetches the file, keeps chain A, removes waters and hetero groups, and computes the pocket center from the bound inhibitor A1DEQ: (-17.13, -25.90, 22.61) Å.

## REST API

Three calls that show the shape. Responses are trimmed here; every real response also carries `xrefs[]` and a full `provenance` block.

**1. A name that matches several organisms.** `ambiguous` lists up to 10 candidates and names the one field that separates them.

```
curl -sG https://api.xwalk.bio/v1/resolve -H "Authorization: Bearer $KEY" --data-urlencode q=p53
```

```json
{"status":"ambiguous","disambiguate_by":"organism","candidates_total":19,
 "candidates":[{"seq_id":"seq:sha256:e3ca60f1…","accession":"P04637","organism":"Homo sapiens (Human)","taxid":9606},
               {"seq_id":"seq:sha256:e95b3ae4…","accession":"P02340","organism":"Mus musculus (Mouse)","taxid":10090}, …],
 "hint":"…"}
```

Pass `organism=9606` and the same call returns `resolved`, with the pinned `seq_id`, the UniProt entries and isoforms, and the candidate structures tiered against the full length.

**2. The best structure for docking into a domain.** `get_structure` takes the `seq:` ID from `resolve_target` and picks one structure for a region and purpose.

```
curl -sG "https://api.xwalk.bio/v1/structure/seq:sha256:dbb4583267ad40a7dfd854ee3c44ce4be38e137d0570e3eb76cf1854a74e7246" \
    -H "Authorization: Bearer $KEY" --data-urlencode "region=Protein kinase" --data-urlencode want=docking
```

```json
{"status":"resolved","id":"str:pdb:9WR8@1.0","tier":"A",
 "reason":"tier A: 2.33 Å X-ray, 100% coverage, no unresolved gaps",
 "method":"X-RAY DIFFRACTION","resolution":2.33,"ligand_bound":true,
 "chains":[{"label_asym_id":"A","auth_asym_id":"A","seq_id":"seq:sha256:1b5cf51f…","uniprot_accessions":["P00533"]}],
 "file_url":"https://files-versioned.wwpdb.org/pdb_versioned/data/entries/wr/pdb_00009wr8/pdb_00009wr8_xyz_v1-0.cif.gz",
 "composition_hash":"sha256:0581d7d6…","annotations":{}, …}
```

Cite `str:pdb:9WR8@1.0`: the version pins the exact file.

**3. A predicted model by its AlphaFold ID, then the file.** The service returns the upstream file URL, not the file.

```
curl -sG https://api.xwalk.bio/v1/structure/str:afdb:AF-P00533-F1 -H "Authorization: Bearer $KEY"
```

```json
{"status":"resolved","id":"str:afdb:AF-P00533-F1@v6","tier":"C",
 "reason":"tier C: predicted, mean pLDDT 75.9 < 85, 100% coverage",
 "file_url":"https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.cif", …}
```

```
curl -s -A "acme-docking/1.0 (ops@acme.example)" -O https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.cif
```

alphafold.ebi.ac.uk answers 403 to curl's default User-Agent; send a descriptive one.

Errors are `{"error":{"code","message","hint"}}` with HTTP 400, 401 or 429. Outcomes (`resolved`, `ambiguous`, `not_found`, `not_available`) are HTTP 200 with `status` in the body. Rate limits come back as `X-RateLimit-{Limit,Remaining}-{Minute,Day}` headers. The response JSON Schema is at `/v1/schema.json`.

## Data sources

The service hosts an index, not structure files. Raw structures stay on their upstream hosts. AlphaFold DB, PDB, UniProt and ESM Atlas data are used under their respective open licenses (CC-BY, CC0 or equivalent), with attribution returned in each response.

## Notes

The [`xwalk`](https://pypi.org/project/xwalk/) name on PyPI is reserved for a future Python client; the unrelated `crosswalk` package is not ours.

## License

The plugin manifests and skills in this repository are under the Apache License 2.0, copyright 2026 Xwalk Bio. See [LICENSE](LICENSE). The Xwalk name and logo are trademarks of Xwalk Bio and are not covered by that license. The hosted service is proprietary. Upstream data keeps its own terms (see [Data sources](#data-sources)).
