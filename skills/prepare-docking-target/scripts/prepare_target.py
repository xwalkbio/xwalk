# /// script
# requires-python = ">=3.10"
# dependencies = ["gemmi>=0.7"]
# ///
"""Prepare a receptor for docking from a get_structure response.

Downloads the structure from its file_url, keeps the target's chain, strips waters
and every hetero group, and reports the pocket center as the centroid of the bound
ligand's heavy atoms. No pocket detection (v1): with no bound ligand, pocket is null.

Usage (all three inputs come from the get_structure response):
    uv run prepare_target.py --id str:pdb:11GV@1.0 \
        --file-url https://files-versioned.wwpdb.org/.../pdb_000011gv_xyz_v1-0.cif.gz \
        --chains A --out receptor.pdb

`--chains` lists the auth_asym_id of every chain whose uniprot_accessions include the
target accession (for an AlphaFold model, A). When several copies qualify, the one in
contact with the best bound ligand is kept.
Prints one JSON object: the pinned ID, chain, ligand, pocket center and output path.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import gemmi

# Components that do not count as a bound ligand: buffers, cryoprotectants, detergents,
# ions, membrane lipids and glycans. Nucleotides and cofactors count, but any other
# ligand is preferred over them. Both lists are kept in sync with the server; do not
# edit by hand.
NON_LIGANDS = frozenset(
    "HOH DOD GOL EDO PEG PGE PG4 1PE P6G MPD PE4 SO4 PO4 ACT ACY FMT CIT TRS EPE MES BME DMS IPA EOH MOH "
    "IMD NO3 SCN MLI TAR CL BR IOD NA K MG CA MN ZN NI CO CD CU FE NH4 LI CS RB SR BA UNX UNL "
    "CLR Y01 OLA OLB OLC 1WV MYR PLM STE POV PCW CDL R16 LMT LMU BNG DMU UND D12 HEX OCT LDA 2CV "
    "NAG NDG MAN BMA FUC GAL SGM 12P BU1 ACM".split()
)
COFACTORS = frozenset(
    "ATP ADP AMP ANP ACP AGS APC ADN VSN 112 GTP GDP GMP GNP GCP GSP 5GP CTP UTP TTP MGF ALF BEF AF3 "
    "SAM SAH SFG NAD NAI NAP NDP FAD FMN HEM HEC COA ACO PLP TPP".split()
)
CONTACT = 4.5  # Å, ligand heavy atom to chain heavy atom
# alphafold.ebi.ac.uk/files answers 403 to clients without a descriptive User-Agent.
USER_AGENT = "xwalk-prepare-docking-target/1.0 (+https://github.com/xwalkbio/xwalk)"


def fetch(url: str) -> gemmi.Structure:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"download failed ({e.code}) for {url}; pass file_url exactly as get_structure returned it")
    if url.endswith(".gz"):
        data = gzip.decompress(data)
    doc = gemmi.cif.read_string(data.decode())
    st = gemmi.make_structure_from_block(doc.sole_block())
    st.setup_entities()
    return st


def heavy(atom: gemmi.Atom) -> bool:
    return atom.element.name not in ("H", "D")


def polymer(res: gemmi.Residue) -> bool:
    # By entity, not HETATM: modified residues (MSE, TPO) are HETATM but part of the chain.
    return res.entity_type == gemmi.EntityType.Polymer


def best_ligand(st: gemmi.Structure, chains: set[str]) -> tuple[gemmi.Chain, gemmi.Residue, str, int] | None:
    """The ligand residue with the most heavy-atom contacts to a target chain, and that chain.
    Any ligand beats a nucleotide or cofactor (an inhibitor next to ADP marks the pocket to
    dock into). Ties go to the larger ligand, then to chain and residue order, so the pick
    is stable."""
    model = st[0]
    ns = gemmi.NeighborSearch(model, st.cell, 5).populate()
    best = None
    for chain in model:
        for res in chain:
            if res.entity_type != gemmi.EntityType.NonPolymer or res.name in NON_LIGANDS:
                continue
            atoms = [a for a in res if heavy(a)]
            contacts: dict[str, int] = {}
            for a in atoms:
                seen = set()
                for mark in ns.find_atoms(a.pos, "\0", radius=CONTACT):
                    cra = mark.to_cra(model)
                    if cra.chain.name in chains and polymer(cra.residue) and heavy(cra.atom):
                        seen.add(cra.chain.name)
                for c in seen:
                    contacts[c] = contacts.get(c, 0) + 1
            if not contacts:
                continue
            chain_name = min(contacts, key=lambda c: (-contacts[c], c))
            key = (res.name in COFACTORS, -contacts[chain_name], -len(atoms), chain.name, res.seqid.num)
            if best is None or key < best[0]:
                best = (key, chain, res, chain_name, contacts[chain_name])
    return None if best is None else best[1:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--id", required=True, help="pinned str: ID from get_structure (echoed for citation)")
    ap.add_argument("--file-url", required=True, help="file_url from get_structure")
    ap.add_argument("--chains", required=True, help="comma-separated auth_asym_ids of the target's chains")
    ap.add_argument("--out", type=Path, required=True, help="where to write the cleaned receptor (.pdb)")
    args = ap.parse_args()

    chains = {c.strip() for c in args.chains.split(",") if c.strip()}
    st = fetch(args.file_url)
    missing = chains - {c.name for c in st[0]}
    if missing:
        sys.exit(f"chains {sorted(missing)} are not in {args.id}; pass auth_asym_id values from get_structure")
    st.remove_hydrogens()
    for i in reversed(range(1, len(st))):
        del st[i]  # model 1 only (v1 scope)
    model = st[0]
    pick = best_ligand(st, chains)
    out: dict = {"id": args.id}
    if pick is None:
        # No bound ligand (e.g. apo GPCRs): there is no pocket detection in v1, so report
        # pocket null with a hint.
        chain = min(chains)
        out.update(chain=chain, ligand=None, pocket=None,
                   hint="No bound ligand contacts the target chain; there is no pocket center without "
                        "detection in v1. Pick a ligand-bound structure (get_structure want=docking) or "
                        "supply the site yourself.")
    else:
        lig_chain, lig, chain, n_contacts = pick
        atoms = [a.pos for a in lig if heavy(a)]
        center = [round(sum(getattr(p, k) for p in atoms) / len(atoms), 3) for k in "xyz"]
        out.update(chain=chain,
                   ligand={"comp_id": lig.name, "auth_chain": lig_chain.name, "auth_seq_id": lig.seqid.num,
                           "heavy_atoms": len(atoms), "contacts": n_contacts},
                   pocket={"center": center, "source": "bound ligand centroid"})

    # Receptor: the chosen chain only, polymer residues only (waters and all ligands removed).
    for name in [c.name for c in model if c.name != out["chain"]]:
        model.remove_chain(name)
    st.remove_ligands_and_waters()
    st.remove_empty_chains()
    st.write_pdb(str(args.out))
    out["receptor"] = str(args.out)
    out["residues"] = sum(len(c) for c in model)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
