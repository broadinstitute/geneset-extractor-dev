#!/usr/bin/env python3
from __future__ import annotations
"""
Filter a deg_long.tsv to immune-related genes and write two subsets:
  - deg_long_immune.tsv     → input for rna_deg_multi → immune gene set
  - deg_long_nonimmune.tsv  → input for rna_deg_multi → non-immune gene set

Immune annotation is based on gene_symbol patterns covering known immune
gene families. Can be supplemented with an external gene list (--immune_genes).

Usage:
  python extract_immune_genesets.py \
    --deg_tsv outputs/analysis/KF-TALL/de_results/deg_long.tsv \
    --out_dir outputs/analysis/KF-TALL/de_results_split \
    [--immune_genes path/to/immune_gene_list.txt]  # one gene symbol per line
"""
import argparse
import csv
import re
import sys
from pathlib import Path

# ── Immune gene annotation ───────────────────────────────────────────────────

# Regex patterns on gene_symbol (case-sensitive, most HGNC symbols are uppercase)
IMMUNE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^IL\d"),           # Interleukins: IL1A, IL2, IL6, IL10, IL17A...
    re.compile(r"^IL\d+R"),         # Interleukin receptors: IL2RA, IL6R...
    re.compile(r"^ILR\d"),
    re.compile(r"^CXCL"),           # CXC chemokines: CXCL1, CXCL10...
    re.compile(r"^CXCR"),           # CXC receptors: CXCR1, CXCR4...
    re.compile(r"^CCL"),            # CC chemokines: CCL2, CCL5...
    re.compile(r"^CCR"),            # CC receptors: CCR2, CCR5...
    re.compile(r"^CX3"),            # CX3CL1, CX3CR1
    re.compile(r"^XCL"),            # XCL1, XCL2
    re.compile(r"^CD\d"),           # CD markers: CD3, CD4, CD8, CD19, CD68...
    re.compile(r"^HLA-"),           # MHC: HLA-A, HLA-B, HLA-DRA...
    re.compile(r"^IGH[VDJ]"),       # Immunoglobulin heavy chain
    re.compile(r"^IGK[VCJ]"),       # Ig kappa
    re.compile(r"^IGL[VCJ]"),       # Ig lambda
    re.compile(r"^TR[ABGD][VDJ]"),  # T-cell receptor
    re.compile(r"^IFN[ABG]"),       # Interferons: IFNA1, IFNB1, IFNG
    re.compile(r"^IFNAR"),          # IFN receptors
    re.compile(r"^IFNGR"),
    re.compile(r"^TNF$"),           # TNF
    re.compile(r"^TNFSF"),          # TNF superfamily ligands: TNFSF10, TNFSF13B...
    re.compile(r"^TNFRSF"),         # TNF receptor superfamily: TNFRSF1A, TNFRSF9...
    re.compile(r"^TLR\d"),          # Toll-like receptors: TLR2, TLR4, TLR9...
    re.compile(r"^KLR[A-Z]"),       # Killer lectin receptors: KLRB1, KLRD1...
    re.compile(r"^NKG2"),           # NK receptors
    re.compile(r"^NCR\d"),          # Natural cytotoxicity receptors: NCR1, NCR3
    re.compile(r"^FCGR"),           # Fc gamma receptors: FCGR1A, FCGR3A
    re.compile(r"^FCER"),           # Fc epsilon receptors
    re.compile(r"^IRF\d"),          # Interferon regulatory factors: IRF1, IRF3, IRF7
    re.compile(r"^STAT\d"),         # STAT transcription factors: STAT1, STAT3...
    re.compile(r"^CSF\d"),          # Colony-stimulating factors: CSF1, CSF2, CSF3
    re.compile(r"^CSFR"),
    re.compile(r"^GZM[ABKMH]"),     # Granzymes: GZMA, GZMB, GZMK...
    re.compile(r"^NLRP"),           # NOD-like receptors: NLRP1, NLRP3
    re.compile(r"^NLR[A-Z]"),
    re.compile(r"^MX\d"),           # Mx proteins (antiviral): MX1, MX2
    re.compile(r"^OAS\d"),          # 2'-5'-oligoadenylate synthetases: OAS1, OAS2...
    re.compile(r"^IFIT\d"),         # Interferon-induced proteins: IFIT1, IFIT3
    re.compile(r"^ISG\d"),          # Interferon-stimulated genes: ISG15, ISG20
]

# Specific named genes not covered by patterns
IMMUNE_SPECIFIC: frozenset[str] = frozenset({
    # Immune checkpoints / coinhibitory
    "PDCD1", "CD274", "PDCD1LG2", "CTLA4", "LAG3", "TIGIT",
    "HAVCR2", "VSIR", "BTLA", "CD160", "CD244", "LILRB1", "LILRB2",
    # Key transcription factors (immune lineage)
    "FOXP3", "RORC", "TBX21", "GATA3", "BCL6", "PAX5", "IKZF1",
    "ETS1", "RUNX1", "RUNX3",
    # Innate immune signaling
    "MYD88", "TICAM1", "STING1", "CGAS", "DDX58", "IFIH1",
    "PYCARD", "CASP1", "CASP4", "CASP5", "NLRC4",
    # B cell specific
    "CD19", "MS4A1", "CD79A", "CD79B", "BLNK", "BTK", "SYK",
    # T cell
    "CD3D", "CD3E", "CD3G", "CD247", "LAT", "ZAP70", "LCK",
    # NK cell
    "NCAM1", "KLRB1", "KLRD1", "PRF1", "FASLG",
    # Macrophage / DC
    "CSF1R", "CD68", "CD163", "MRC1", "CD14", "ITGAM", "ITGAX",
    "CLEC4A", "CLEC4C", "SIGLEC1",
    # Mast cell / basophil
    "KIT", "FCER1A", "MS4A2",
    # Complement
    "C1QA", "C1QB", "C1QC", "C3", "C3AR1", "C5", "C5AR1",
    "CFB", "CFD", "CFH", "CFI", "CFP",
    "CR1", "CR2", "CD46", "CD55", "CD59",
    # Cytokines not covered by patterns
    "TGFB1", "TGFB2", "TGFB3", "VEGFA", "VEGFB",
    # Key antigen presentation
    "B2M", "CIITA", "TAPBP", "TAP1", "TAP2",
    # Chemokine receptors not covered
    "ACKR1", "ACKR3", "ACKR4",
    # ISG15 pathway
    "ISG15", "UBE2L6", "HERC5",
    # Type I IFN response (specific)
    "RSAD2", "SAMHD1", "TRIM5", "TRIM22", "BST2",
})


def is_immune(gene_symbol: str) -> bool:
    if not gene_symbol:
        return False
    if gene_symbol in IMMUNE_SPECIFIC:
        return True
    for pat in IMMUNE_PATTERNS:
        if pat.search(gene_symbol):
            return True
    return False


def split_deg(deg_tsv: Path, out_dir: Path, immune_genes_extra: set[str] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []
    with open(deg_tsv) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    if "gene_symbol" not in fieldnames:
        print("WARNING: 'gene_symbol' column not found — immune annotation will be minimal", file=sys.stderr)

    extra = immune_genes_extra or set()

    immune_rows: list[dict[str, str]] = []
    nonimmune_rows: list[dict[str, str]] = []
    for row in all_rows:
        sym = row.get("gene_symbol", "").strip()
        if is_immune(sym) or sym in extra:
            immune_rows.append(row)
        else:
            nonimmune_rows.append(row)

    n_total = len(all_rows)
    n_immune = len(immune_rows)
    print(f"  Total genes: {n_total}", file=sys.stderr)
    print(f"  Immune: {n_immune} ({100*n_immune/max(n_total,1):.1f}%)", file=sys.stderr)
    print(f"  Non-immune: {len(nonimmune_rows)}", file=sys.stderr)

    def _write(path: Path, rows: list[dict[str, str]]) -> None:
        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    _write(out_dir / "deg_long_immune.tsv", immune_rows)
    _write(out_dir / "deg_long_nonimmune.tsv", nonimmune_rows)
    print(f"Written: {out_dir}/deg_long_immune.tsv + deg_long_nonimmune.tsv", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--deg_tsv", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--immune_genes", default=None, help="Optional extra immune gene list (one symbol per line)")
    args = p.parse_args()

    extra: set[str] = set()
    if args.immune_genes:
        with open(args.immune_genes) as fh:
            extra = {line.strip() for line in fh if line.strip()}
        print(f"Loaded {len(extra)} extra immune genes from {args.immune_genes}", file=sys.stderr)

    split_deg(
        deg_tsv=Path(args.deg_tsv),
        out_dir=Path(args.out_dir),
        immune_genes_extra=extra,
    )


if __name__ == "__main__":
    main()
