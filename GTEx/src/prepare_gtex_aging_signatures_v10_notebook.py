#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a v10-adapted executable copy of GTExAgingSignatures.ipynb."
    )
    parser.add_argument("--source_notebook", required=True)
    parser.add_argument("--counts_gct", required=True)
    parser.add_argument("--sample_metadata_tsv", required=True)
    parser.add_argument("--subject_metadata_tsv", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--output_notebook", required=True)
    return parser


def code_cell(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.rstrip("\n").splitlines()],
    }


def markdown_cell(source: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source.rstrip("\n").splitlines()],
    }


def r_helper_script() -> str:
    return r"""suppressPackageStartupMessages({
  library(edgeR)
  library(limma)
})

args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 3) {
  stop("expected args: <counts_tsv> <sample_meta_tsv> <sigs_dir>")
}

counts_tsv <- args[[1]]
sample_meta_tsv <- args[[2]]
sigs_dir <- args[[3]]

dir.create(sigs_dir, recursive=TRUE, showWarnings=FALSE)

counts <- read.delim(counts_tsv, check.names=FALSE)
sample_meta <- read.delim(sample_meta_tsv, check.names=FALSE)

rownames(counts) <- counts[[1]]
counts <- counts[, setdiff(colnames(counts), "Gene"), drop=FALSE]
tissue_names <- unique(sample_meta$SMTS)

for (tissue in tissue_names) {
  sub_meta <- sample_meta[sample_meta$SMTS == tissue, , drop=FALSE]
  sample_ids <- as.character(sub_meta$SAMPID)
  data_df <- counts[, sample_ids, drop=FALSE]
  y_all <- DGEList(counts=as.matrix(data_df))
  keep <- filterByExpr(y_all)
  data_df <- data_df[keep, , drop=FALSE]

  if (sum(sub_meta$age == "20-29") < 3) {
    message(tissue, " not enough healthy samples")
    next
  }

  for (agegrp in unique(sub_meta$age)) {
    if (agegrp == "20-29") {
      next
    }
    if (sum(sub_meta$age == agegrp) < 3) {
      next
    }

    min_samp <- min(sum(sub_meta$age == "20-29"), sum(sub_meta$age == agegrp))
    set.seed(1)
    ctl_ids <- sample(sub_meta$SAMPID[sub_meta$age == "20-29"], min_samp)
    set.seed(1)
    pert_ids <- sample(sub_meta$SAMPID[sub_meta$age == agegrp], min_samp)
    selected_ids <- c(ctl_ids, pert_ids)

    subset_mat <- as.matrix(data_df[, selected_ids, drop=FALSE])
    group <- factor(c(rep("control", length(ctl_ids)), rep("case", length(pert_ids))), levels=c("control", "case"))
    y <- DGEList(counts=subset_mat)
    y <- calcNormFactors(y)
    design <- model.matrix(~ group)
    v <- voom(y, design, plot=FALSE)
    fit <- lmFit(v, design)
    fit <- eBayes(fit)
    tt <- topTable(fit, coef="groupcase", number=Inf, sort.by="none")
    tt$gene_symbol <- rownames(tt)

    out_name <- paste0("GTEx_", gsub(" ", "", tissue), "_20-29_vs_", agegrp, ".tsv")
    write.table(tt, file=file.path(sigs_dir, out_name), sep="\t", quote=FALSE)
  }
}
"""


def main() -> int:
    args = build_parser().parse_args()
    source_notebook = Path(args.source_notebook).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_notebook = Path(args.output_notebook).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    original = json.loads(source_notebook.read_text(encoding="utf-8"))
    metadata = copy.deepcopy(original.get("metadata", {}))

    counts_gct = str(Path(args.counts_gct).resolve())
    sample_metadata_tsv = str(Path(args.sample_metadata_tsv).resolve())
    subject_metadata_tsv = str(Path(args.subject_metadata_tsv).resolve())
    gtf_path = str(Path(args.gtf).resolve())
    output_dir_text = str(output_dir)
    r_helper_path = output_dir / "run_gtex_aging_signatures_v10.R"
    r_helper_path.write_text(r_helper_script(), encoding="utf-8", newline="\n")

    cells: list[dict[str, object]] = [
        markdown_cell(
            "# GTEx Aging Signatures (v10 Adapted)\n"
            "This notebook is an executable v10-adapted copy of `GTExAgingSignatures.ipynb`.\n"
            "It preserves the core aging-signature generation logic needed to emit the GMT files."
        ),
        code_cell(
            f"""
import gzip
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

COUNTS_GCT = r"{counts_gct}"
SAMPLE_METADATA_TSV = r"{sample_metadata_tsv}"
SUBJECT_METADATA_TSV = r"{subject_metadata_tsv}"
GTF_PATH = r"{gtf_path}"
OUTPUT_DIR = Path(r"{output_dir_text}")
SIGS_DIR = OUTPUT_DIR / "GTEx_AgeComparison_Tissue_filtered"
DOWNLOADS_DIR = OUTPUT_DIR / "downloads"
RSCRIPT_BIN = os.environ.get("RSCRIPT_BIN", "Rscript")
R_HELPER = OUTPUT_DIR / "run_gtex_aging_signatures_v10.R"
SIGS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
"""
        ),
        code_cell(
            """
gtexagingsigs = pd.read_csv(COUNTS_GCT, sep='\\t', skiprows=2, compression='infer')
gtexagingsigs
"""
        ),
        code_cell(
            """
records = []
opener = gzip.open if str(GTF_PATH).endswith('.gz') else open
with opener(GTF_PATH, 'rt', encoding='utf-8') as handle:
    for line in handle:
        if not line or line.startswith('#'):
            continue
        parts = line.rstrip('\\n').split('\\t')
        if len(parts) != 9 or parts[2] != 'gene':
            continue
        attrs = {}
        for item in parts[8].split(';'):
            item = item.strip()
            if not item or ' ' not in item:
                continue
            key, value = item.split(' ', 1)
            attrs[key] = value.strip().strip('\"')
        gene_id = attrs.get('gene_id', '').split('.')[0]
        gene_name = attrs.get('gene_name', '')
        if gene_id and gene_name:
            records.append((gene_id, gene_name))

gene_info = pd.DataFrame(records, columns=['ensembl', 'Symbol']).drop_duplicates(subset=['ensembl'], keep='first').set_index('ensembl')
gene_info
"""
        ),
        code_cell(
            """
to_keep = []
for g in gtexagingsigs['Name']:
    if g.split('.')[0] in gene_info.index:
        to_keep.append(g)

len(to_keep)
"""
        ),
        code_cell(
            """
gtexagingsigs = gtexagingsigs.set_index('Name').drop(columns=['Description'])
gtexagingsigs = gtexagingsigs.T.get(to_keep).T
gtexagingsigs
"""
        ),
        code_cell(
            """
var_df = gtexagingsigs.var(axis=1).to_frame(name='Var')
var_df['Ens'] = var_df.index.map(lambda x: x.split('.')[0])
var_df
"""
        ),
        code_cell(
            """
keep = var_df.sort_values(by=['Ens', 'Var'], ascending=True).drop_duplicates(subset=['Ens'], keep='last').index
gtexagingsigs = gtexagingsigs.T.get(keep).T
gtexagingsigs
"""
        ),
        code_cell(
            """
gene_info = gene_info.reset_index().drop_duplicates('ensembl').set_index('ensembl')
gtexagingsigs.index = gtexagingsigs.index.map(lambda x: gene_info.loc[x.split('.')[0], 'Symbol'])
gtexagingsigs
"""
        ),
        code_cell(
            """
sample_meta = pd.read_csv(SAMPLE_METADATA_TSV, sep='\\t')
sample_meta['sub'] = sample_meta['SAMPID'].apply(lambda x: '-'.join(x.split('-')[:2]))
sample_meta = sample_meta[['SAMPID', 'SMTS', 'sub']].set_index('SAMPID')
sample_meta
"""
        ),
        code_cell(
            """
meta = pd.read_csv(SUBJECT_METADATA_TSV, sep='\\t')
meta = meta.set_index('SUBJID')

sample_meta['age'] = [meta.loc[row.sub, 'AGE'] for row in sample_meta.itertuples()]
sample_meta['sex'] = [meta.loc[row.sub, 'SEX'] for row in sample_meta.itertuples()]
sample_meta = sample_meta[sample_meta.index.map(lambda x: x in gtexagingsigs.columns)]
sample_meta
"""
        ),
        code_cell(
            """
counts_for_r = gtexagingsigs.copy()
counts_for_r.index.name = 'Gene'
counts_for_r.reset_index().to_csv(OUTPUT_DIR / 'gtexagingsigs_symbol_counts.tsv', sep='\\t', index=False)
sample_meta_for_r = sample_meta.reset_index().rename(columns={'index': 'SAMPID'})
sample_meta_for_r.to_csv(OUTPUT_DIR / 'gtexagingsigs_sample_meta.tsv', sep='\\t', index=False)
subprocess.run(
    [
        RSCRIPT_BIN,
        str(R_HELPER),
        str(OUTPUT_DIR / 'gtexagingsigs_symbol_counts.tsv'),
        str(OUTPUT_DIR / 'gtexagingsigs_sample_meta.tsv'),
        str(SIGS_DIR),
    ],
    check=True,
)
"""
        ),
        code_cell(
            """
gtexagingsigs = pd.DataFrame(columns=['gene_symbol', 'adj.P.Val', 'Aging Signature', 'Threshold'])
for sig in tqdm(os.listdir(SIGS_DIR)):
    sigframe = pd.read_csv(SIGS_DIR / sig, sep='\\t', index_col='gene_symbol')
    sig = sig.replace('.tsv', '')
    sigframe = sigframe[sigframe['adj.P.Val'] < 0.05]
    sigframe['Aging Signature'] = sig.replace('_', ' ')
    sigframe['Threshold'] = sigframe['logFC'].apply(lambda x: 1 if x > 0 else -1)
    sigframe = sigframe.reset_index(names='gene_symbol')[['gene_symbol', 'adj.P.Val', 'Aging Signature', 'Threshold']]
    gtexagingsigs = pd.concat([gtexagingsigs, sigframe])

gtexagingsigs = gtexagingsigs.sort_values('adj.P.Val').groupby(['Aging Signature', 'Threshold']).head(250).reset_index(drop=True)
gtexagingsigs
"""
        ),
        markdown_cell("### Gene Set Exports"),
        code_cell(
            """
gtexagingsigs = gtexagingsigs[['gene_symbol', 'Aging Signature', 'adj.P.Val', 'Threshold']]
gtexagingsigs.columns = ['Gene', 'Aging Signature', '-logP', 'threshold']
gtexagingsigs['-logP'] = gtexagingsigs['-logP'].apply(np.log) * -1 * gtexagingsigs['threshold']
gtexagingsigs = gtexagingsigs.reset_index(drop=True)
gtexagingsigs
"""
        ),
        code_cell(
            """
ternarymatrix = pd.crosstab(gtexagingsigs['Gene'], gtexagingsigs['Aging Signature'], gtexagingsigs['threshold'], aggfunc=max).replace(np.nan, 0).astype(int)
ternarymatrix.to_csv(DOWNLOADS_DIR / 'gene_attribute_matrix.txt.gz', sep='\\t', compression='gzip')
ternarymatrix
"""
        ),
        code_cell(
            """
with open(DOWNLOADS_DIR / 'gene_set_library_up_crisp.gmt', 'w', encoding='utf-8') as f:
    arr = ternarymatrix.reset_index(drop=True).to_numpy(dtype=np.int_)
    attributes = ternarymatrix.columns
    w, h = arr.shape
    for i in tqdm(range(h)):
        genes = [*ternarymatrix.index[arr[:, i] == 1]]
        if len(genes) >= 5:
            print(attributes[i], *genes, sep='\\t', end='\\n', file=f)
"""
        ),
        code_cell(
            """
with open(DOWNLOADS_DIR / 'gene_set_library_dn_crisp.gmt', 'w', encoding='utf-8') as f:
    arr = ternarymatrix.reset_index(drop=True).to_numpy(dtype=np.int_)
    attributes = ternarymatrix.columns
    w, h = arr.shape
    for i in tqdm(range(h)):
        genes = [*ternarymatrix.index[arr[:, i] == -1]]
        if len(genes) >= 5:
            print(attributes[i], *genes, sep='\\t', end='\\n', file=f)
"""
        ),
    ]

    notebook = {
        "cells": cells,
        "metadata": metadata,
        "nbformat": original.get("nbformat", 4),
        "nbformat_minor": original.get("nbformat_minor", 5),
    }
    output_notebook.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
