#!/usr/bin/env python3
"""
Standalone conversion of:
  HarmonizomePythonScripts/GTEx/Tissue-Specific Aging Signatures/
  GTExAgingSignatures.ipynb

This version uses the notebook-appropriate raw GTEx V8 gene READS matrix and
Ma'ayan Lab's limma-voom helper functions rather than TPM or characteristic
direction.

The notebook-level analysis preserved here is:

  1. Load GTEx V8 gene read counts GCT.
  2. Load GTEx sample attributes and subject phenotypes.
  3. Map GTEx samples to subject age groups and tissues.
  4. Map GTEx genes to human symbols using human_gene_info.
  5. For each tissue and age comparison against 20-29:
       - balance the 20-29 and comparison groups using random_state=1
       - filter count matrix with maayanlab_bioinformatics.normalization.filter.filter_by_expr
       - run maayanlab_bioinformatics.dge.limma_voom_differential_expression
       - write the limma-voom result TSV
  6. Optionally build combined GMT/matrix-style outputs from the per-comparison
     limma-voom tables.

Important:
  - The expression input is the GTEx V8 raw reads GCT:
      GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct[.gz]
  - Do not use the TPM file if your goal is notebook-equivalent limma-voom.
  - maayanlab-bioinformatics with R/rpy2/limma/edgeR/statmod must be installed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


AGE_ORDER = ["20-29", "30-39", "40-49", "50-59", "60-69", "70-79"]
REFERENCE_AGE = "20-29"


# ---------------------------------------------------------------------------
# Notebook cell: imports from maayanlab_bioinformatics
# ---------------------------------------------------------------------------

def import_maayanlab_functions():
    """
    Import Ma'ayan Lab helper functions at runtime so --help works even before
    the analysis environment is fully installed.
    """
    try:
        from maayanlab_bioinformatics.normalization.filter import filter_by_expr
        from maayanlab_bioinformatics.dge.limma_voom import (
            limma_voom_differential_expression,
            up_down_from_limma_voom,
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not import maayanlab_bioinformatics limma-voom helpers.\n"
            "Install the package and its R dependencies, for example:\n"
            '  pip install "maayanlab-bioinformatics[all] @ '
            'git+https://github.com/MaayanLab/maayanlab-bioinformatics.git"\n'
            "  python -m maayanlab_bioinformatics.setup.R\n"
            "You also need R packages used by limma_voom.py: limma, edgeR, "
            "statmod, DESeq2, R.utils, and RCurl."
        ) from exc

    return filter_by_expr, limma_voom_differential_expression, up_down_from_limma_voom


# ---------------------------------------------------------------------------
# Notebook cell: general utilities
# ---------------------------------------------------------------------------

def eprint(*args: object) -> None:
    print(*args, file=sys.stderr, flush=True)


def mkdirp(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def open_text(path: Path, mode: str = "rt"):
    if str(path).endswith(".gz"):
        return gzip.open(path, mode)
    return open(path, mode)


def sanitize_tissue_label(value: str) -> str:
    """
    Harmonizome-style compact label:
      'Blood Vessel' -> 'BloodVessel'
      'Adipose Tissue' -> 'AdiposeTissue'
    """
    value = str(value).strip()
    value = re.sub(r"[^A-Za-z0-9]+", " ", value)
    return "".join(part for part in value.split() if part)


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "comparison"


def sample_to_subject_id(sample_id: str) -> str:
    parts = str(sample_id).split("-")
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return str(sample_id)


def parse_age_group(value: object) -> str | None:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s in AGE_ORDER:
        return s

    # Defensive support for numeric ages, although GTEx V8 public phenotype
    # files typically provide decade bins.
    m = re.search(r"(\d+)", s)
    if not m:
        return None
    age = int(m.group(1))
    if 20 <= age <= 29:
        return "20-29"
    if 30 <= age <= 39:
        return "30-39"
    if 40 <= age <= 49:
        return "40-49"
    if 50 <= age <= 59:
        return "50-59"
    if 60 <= age <= 69:
        return "60-69"
    if 70 <= age <= 79:
        return "70-79"
    return None


def choose_column(df: pd.DataFrame, candidates: Sequence[str], label: str) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        f"Could not find {label} column. Tried: {', '.join(candidates)}. "
        f"Available columns begin: {', '.join(map(str, df.columns[:30]))}"
    )


def strip_ensembl_version(gene_id: object) -> str:
    s = str(gene_id).strip()
    return s.split(".")[0]


def gct_header_columns(path: Path) -> list[str]:
    with open_text(path, "rt") as fh:
        _version = fh.readline()
        _dims = fh.readline()
        header = fh.readline().rstrip("\n").split("\t")
    return header


# ---------------------------------------------------------------------------
# Notebook cell: load metadata
# ---------------------------------------------------------------------------

def read_table(path: Path) -> pd.DataFrame:
    eprint(f"[load] {path}")
    return pd.read_csv(path, sep="\t", low_memory=False)


def build_sample_metadata(sample_attr: pd.DataFrame, subject_pheno: pd.DataFrame) -> pd.DataFrame:
    sample_col = choose_column(sample_attr, ["SAMPID", "sample_id", "SampleID"], "sample id")
    smts_col = choose_column(sample_attr, ["SMTS", "smts", "tissue", "TISSUE"], "SMTS/tissue")
    smtsd_col = None
    for candidate in ["SMTSD", "smtsd", "tissue_detail", "TISSUE_DETAIL"]:
        if candidate in sample_attr.columns:
            smtsd_col = candidate
            break

    subj_col = choose_column(subject_pheno, ["SUBJID", "subject_id", "SubjectID"], "subject id")
    age_col = choose_column(subject_pheno, ["AGE", "age", "Age"], "age")
    sex_col = None
    for candidate in ["SEX", "sex", "Sex"]:
        if candidate in subject_pheno.columns:
            sex_col = candidate
            break

    meta = sample_attr[[sample_col, smts_col] + ([smtsd_col] if smtsd_col else [])].copy()
    meta = meta.rename(columns={sample_col: "SAMPID", smts_col: "SMTS"})
    if smtsd_col:
        meta = meta.rename(columns={smtsd_col: "SMTSD"})
    else:
        meta["SMTSD"] = meta["SMTS"]

    meta["SUBJID"] = meta["SAMPID"].map(sample_to_subject_id)

    subj_cols = [subj_col, age_col] + ([sex_col] if sex_col else [])
    subj = subject_pheno[subj_cols].copy()
    rename = {subj_col: "SUBJID", age_col: "AGE"}
    if sex_col:
        rename[sex_col] = "SEX"
    subj = subj.rename(columns=rename)
    if "SEX" not in subj.columns:
        subj["SEX"] = ""

    meta = meta.merge(subj, on="SUBJID", how="left")
    meta["AGE_GROUP"] = meta["AGE"].map(parse_age_group)
    meta["TISSUE"] = meta["SMTS"].map(sanitize_tissue_label)
    meta = meta.dropna(subset=["AGE_GROUP", "TISSUE"])
    meta = meta[meta["AGE_GROUP"].isin(AGE_ORDER)].copy()
    return meta


# ---------------------------------------------------------------------------
# Notebook cell: gene mapping from human_gene_info
# ---------------------------------------------------------------------------

def read_human_gene_info_ensembl_mapping(path: Path) -> dict[str, str]:
    """
    Notebook-style human_gene_info parsing.

    GTExAgingSignatures.ipynb uses human_gene_info as an Ensembl -> Symbol map:
      - read human_gene_info
      - restrict to #tax_id == 9606
      - keep Symbol and dbXrefs
      - extract Ensembl:ENSG... from dbXrefs
      - strip anything after a pipe
      - map GTEx versionless Ensembl IDs to Symbol

    This intentionally does NOT use GTEx Description fallback, Synonyms, or
    permissive alias mapping, because those are not 1-to-1 with the notebook.
    """
    eprint(f"[load] human_gene_info: {path}")
    df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)

    if "#tax_id" in df.columns:
        df = df[df["#tax_id"].astype(str) == "9606"].copy()

    for col in ["Symbol", "dbXrefs"]:
        if col not in df.columns:
            raise ValueError(
                f"human_gene_info is missing required column {col!r}. "
                f"Available columns begin: {', '.join(map(str, df.columns[:20]))}"
            )

    ensembl_re = re.compile(r"Ensembl:([^|]+)")
    mapping: dict[str, str] = {}

    for dbxrefs, symbol in df[["dbXrefs", "Symbol"]].dropna().itertuples(index=False):
        symbol = str(symbol).strip()
        if not symbol or symbol == "-" or symbol.lower() == "nan":
            continue
        m = ensembl_re.search(str(dbxrefs))
        if not m:
            continue
        ensembl = m.group(1).split("|")[0].strip()
        ensembl = strip_ensembl_version(ensembl)
        if ensembl:
            mapping.setdefault(ensembl, symbol)

    eprint(f"[load] parsed {len(mapping):,} Ensembl-to-symbol mappings")
    return mapping


# ---------------------------------------------------------------------------
# Notebook cell: read GTEx read-count GCT subsets
# ---------------------------------------------------------------------------

def validate_reads_gct_name(path: Path, strict: bool) -> None:
    name = path.name
    if "gene_reads.gct" not in name:
        msg = (
            "This notebook-equivalent script expects the GTEx V8 raw gene reads "
            "GCT, e.g. GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz. "
            f"Got: {path}"
        )
        if strict:
            raise ValueError(msg)
        eprint(f"[warn] {msg}")


def read_gct_subset(path: Path, sample_ids: Sequence[str]) -> pd.DataFrame:
    """
    Read Name, Description, and only the selected sample columns from the GCT.
    This preserves the notebook input while avoiding full-GCT memory use.
    """
    requested = set(sample_ids)
    header = gct_header_columns(path)
    present_samples = [c for c in header if c in requested]
    usecols = ["Name", "Description"] + present_samples
    if not present_samples:
        raise ValueError("No requested sample columns were present in the GCT.")

    eprint(f"[load] {path.name}; selected samples={len(present_samples):,}")
    return pd.read_csv(path, sep="\t", skiprows=2, usecols=usecols, low_memory=False)


def prepare_count_matrix(
    gct_subset: pd.DataFrame,
    sample_ids: Sequence[str],
    ensembl_to_symbol: Mapping[str, str],
    drop_unmapped: bool = True,
) -> pd.DataFrame:
    """
    Prepare a genes x samples raw count matrix using notebook-style mapping.

    Notebook-equivalent preprocessing:
      1. Use GTEx GCT Name as the source Ensembl ID.
      2. Strip Ensembl version suffix to get the base Ensembl ID.
      3. Keep only rows whose base Ensembl ID is in human_gene_info mapping.
      4. If multiple versioned rows share the same base Ensembl ID, keep the row
         with highest variance across the loaded samples. This mirrors:
             var_df = gtexagingsigs.var(axis=1).to_frame(name='Var')
             var_df['Ens'] = var_df.index.map(lambda x: x.split('.')[0])
             keep = var_df.sort_values(by=['Ens','Var'], ascending=True)
                          .drop_duplicates(subset=['Ens'], keep='last').index
      5. Rename rows to human gene symbols.

    Important: this does NOT collapse duplicate symbols by sum. The notebook
    removes duplicate Ensembl IDs before symbol renaming.
    """
    samples = [s for s in sample_ids if s in gct_subset.columns]
    if not samples:
        raise ValueError("No overlapping samples between GCT subset and metadata.")

    work = gct_subset[["Name"] + samples].copy()
    work["Ens"] = work["Name"].map(strip_ensembl_version)

    if ensembl_to_symbol:
        work = work[work["Ens"].isin(ensembl_to_symbol)].copy()
    elif drop_unmapped:
        raise ValueError("No Ensembl-to-symbol mapping available, but notebook mode requires one.")

    counts_only = work.loc[:, samples].apply(pd.to_numeric, errors="coerce").fillna(0)
    work["_Var"] = counts_only.var(axis=1)

    # Sort ascending and keep last to match notebook behavior.
    keep_idx = (
        work[["Ens", "_Var"]]
        .sort_values(by=["Ens", "_Var"], ascending=True)
        .drop_duplicates(subset=["Ens"], keep="last")
        .index
    )

    kept = work.loc[keep_idx, ["Ens"] + samples].copy()
    counts = kept.loc[:, samples].apply(pd.to_numeric, errors="coerce").fillna(0)
    counts.index = kept["Ens"].map(lambda x: ensembl_to_symbol.get(x, x)).astype(str)
    counts.index.name = "gene_symbol"

    # The notebook does not explicitly handle duplicated symbols after mapping.
    # If human_gene_info maps two distinct Ensembl IDs to the same Symbol, pandas
    # can carry duplicate indices. limma/R prefers unique row names, so keep the
    # highest-variance representative by symbol in the same spirit as the
    # notebook's duplicate-Ensembl handling.
    if counts.index.has_duplicates:
        tmp = counts.copy()
        tmp["_Var"] = tmp.var(axis=1)
        tmp["_gene_symbol"] = tmp.index
        keep_symbol_idx = (
            tmp[["_gene_symbol", "_Var"]]
            .sort_values(by=["_gene_symbol", "_Var"], ascending=True)
            .drop_duplicates(subset=["_gene_symbol"], keep="last")
            .index
        )
        counts = counts.loc[keep_symbol_idx]
        counts = counts[~counts.index.duplicated(keep="last")]

    return counts


def read_count_matrix_for_samples_lowmem(
    path: Path,
    sample_ids: Sequence[str],
    ensembl_to_symbol: Mapping[str, str],
    chunksize: int = 1000,
) -> pd.DataFrame:
    """
    Low-memory replacement for read_gct_subset() + prepare_count_matrix().

    It streams the GTEx GCT by gene-row chunks and returns only the final
    mapped gene_symbol x selected_samples raw count matrix for one tissue.

    This reduces peak memory because it never materializes the unprocessed
    GCT subset containing all selected samples plus unmapped rows.
    """
    requested = set(sample_ids)
    header = gct_header_columns(path)
    present_samples = [c for c in header if c in requested]
    if not present_samples:
        raise ValueError("No requested sample columns were present in the GCT.")

    usecols = ["Name", "Description"] + present_samples
    eprint(
        f"[load-lowmem] {path.name}; selected samples={len(present_samples):,}; "
        f"chunksize={chunksize:,}"
    )

    chunks: list[pd.DataFrame] = []
    rows_seen = 0
    rows_kept = 0

    reader = pd.read_csv(
        path,
        sep="\t",
        skiprows=2,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    )

    for i, chunk in enumerate(reader, start=1):
        rows_seen += int(chunk.shape[0])

        work = chunk[["Name"] + present_samples].copy()
        work["Ens"] = work["Name"].map(strip_ensembl_version)
        work = work[work["Ens"].isin(ensembl_to_symbol)].copy()
        if work.empty:
            continue

        counts_only = work.loc[:, present_samples].apply(pd.to_numeric, errors="coerce").fillna(0)
        work["_Var"] = counts_only.var(axis=1)

        # Resolve duplicate versioned Ensembl IDs within this chunk.
        keep_idx = (
            work[["Ens", "_Var"]]
            .sort_values(by=["Ens", "_Var"], ascending=True)
            .drop_duplicates(subset=["Ens"], keep="last")
            .index
        )

        kept = work.loc[keep_idx, ["Ens", "_Var"]].copy()
        counts = counts_only.loc[keep_idx, :].copy()
        counts.insert(0, "_Var", kept["_Var"].to_numpy())
        counts.insert(0, "Ens", kept["Ens"].to_numpy())
        chunks.append(counts)
        rows_kept += int(counts.shape[0])

        if i == 1 or i % 10 == 0:
            eprint(
                f"[load-lowmem] chunk={i}; rows_seen={rows_seen:,}; "
                f"mapped_rows_kept~={rows_kept:,}"
            )

    if not chunks:
        raise RuntimeError("No mapped Ensembl genes were retained from the GCT.")

    work_all = pd.concat(chunks, axis=0, ignore_index=True)
    del chunks

    # Resolve duplicate Ensembl IDs across chunks.
    keep_idx = (
        work_all[["Ens", "_Var"]]
        .sort_values(by=["Ens", "_Var"], ascending=True)
        .drop_duplicates(subset=["Ens"], keep="last")
        .index
    )
    work_all = work_all.loc[keep_idx, :].copy()

    counts = work_all.loc[:, present_samples].apply(pd.to_numeric, errors="coerce").fillna(0)
    counts.index = work_all["Ens"].map(lambda x: ensembl_to_symbol.get(x, x)).astype(str)
    counts.index.name = "gene_symbol"

    # Resolve duplicated symbols globally by keeping highest-variance representative.
    if counts.index.has_duplicates:
        tmp = counts.copy()
        tmp["_Var"] = tmp.var(axis=1)
        tmp["_gene_symbol"] = tmp.index
        keep_symbol_idx = (
            tmp[["_gene_symbol", "_Var"]]
            .sort_values(by=["_gene_symbol", "_Var"], ascending=True)
            .drop_duplicates(subset=["_gene_symbol"], keep="last")
            .index
        )
        counts = counts.loc[keep_symbol_idx]
        counts = counts[~counts.index.duplicated(keep="last")]

    eprint(f"[load-lowmem] final matrix: genes={counts.shape[0]:,}; samples={counts.shape[1]:,}")
    return counts



# ---------------------------------------------------------------------------
# Notebook cell: balanced age comparisons + limma-voom
# ---------------------------------------------------------------------------

@dataclass
class ComparisonAudit:
    tissue: str
    age_group: str
    attribute: str
    n_reference_available: int
    n_case_available: int
    n_reference_used: int
    n_case_used: int
    n_genes_before_filter: int
    n_genes_after_filter: int
    status: str
    result_file: str


def balanced_samples(
    ref_samples_all: Sequence[str],
    case_samples_all: Sequence[str],
    random_state: int,
) -> tuple[list[str], list[str]]:
    """
    Match notebook-style balancing:
      use the smaller of 20-29 and comparison-age sample counts,
      sample each group with random_state=1.
    """
    n = min(len(ref_samples_all), len(case_samples_all))
    if n <= 0:
        return [], []

    ref = pd.Series(list(ref_samples_all)).sample(n=n, random_state=random_state, replace=False).tolist()
    case = pd.Series(list(case_samples_all)).sample(n=n, random_state=random_state, replace=False).tolist()
    return ref, case


def run_one_comparison(
    counts_gene_by_sample: pd.DataFrame,
    tissue: str,
    age_group: str,
    ref_samples_all: Sequence[str],
    case_samples_all: Sequence[str],
    output_dir: Path,
    random_state: int,
    min_samples_per_group: int,
    limma_voom_func,
    limma_filter_genes: bool,
    limma_voom_design: bool,
    save_filtered_counts: bool,
) -> ComparisonAudit:
    attribute = f"GTEx {tissue} {REFERENCE_AGE} vs {age_group}"
    filename_base = safe_filename(attribute)
    result_path = output_dir / "limma_voom_results" / f"{filename_base}.tsv"

    ref_samples, case_samples = balanced_samples(ref_samples_all, case_samples_all, random_state=random_state)

    if len(ref_samples) < min_samples_per_group or len(case_samples) < min_samples_per_group:
        return ComparisonAudit(
            tissue=tissue,
            age_group=age_group,
            attribute=attribute,
            n_reference_available=len(ref_samples_all),
            n_case_available=len(case_samples_all),
            n_reference_used=len(ref_samples),
            n_case_used=len(case_samples),
            n_genes_before_filter=int(counts_gene_by_sample.shape[0]),
            n_genes_after_filter=0,
            status=f"skipped: n per group < {min_samples_per_group}",
            result_file="",
        )

    selected = ref_samples + case_samples
    mat = counts_gene_by_sample.loc[:, selected].copy()
    n_before = int(mat.shape[0])
    n_after = n_before

    if save_filtered_counts:
        filt_path = output_dir / "filtered_counts" / f"{filename_base}.filtered_counts.tsv.gz"
        mat.to_csv(filt_path, sep="\t", compression="gzip")

    ctl_df = mat.loc[:, ref_samples]
    pert_df = mat.loc[:, case_samples]

    eprint(
        f"[limma-voom] {attribute}; "
        f"n_ref={len(ref_samples)}; n_case={len(case_samples)}; tissue-filtered genes={n_after:,}"
    )

    res = limma_voom_func(
        controls_mat=ctl_df,
        cases_mat=pert_df,
        all_data_mat=mat,
        filter_genes=limma_filter_genes,
        voom_design=limma_voom_design,
    )

    res = res.copy()
    res.index.name = "gene_symbol"
    res.to_csv(result_path, sep="\t")

    return ComparisonAudit(
        tissue=tissue,
        age_group=age_group,
        attribute=attribute,
        n_reference_available=len(ref_samples_all),
        n_case_available=len(case_samples_all),
        n_reference_used=len(ref_samples),
        n_case_used=len(case_samples),
        n_genes_before_filter=n_before,
        n_genes_after_filter=n_after,
        status="ok",
        result_file=str(result_path),
    )


# ---------------------------------------------------------------------------
# Notebook cell: optional combined outputs
# ---------------------------------------------------------------------------

def read_limma_result(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "gene_symbol" in df.columns:
        df = df.set_index("gene_symbol")
    elif df.columns[0] != "gene_symbol":
        df = df.rename(columns={df.columns[0]: "gene_symbol"}).set_index("gene_symbol")
    return df


def build_t_stat_matrix(audit: pd.DataFrame) -> pd.DataFrame:
    ok = audit[audit["status"] == "ok"].copy()
    series = {}
    for _, row in ok.iterrows():
        path = Path(row["result_file"])
        if not path.exists():
            continue
        df = read_limma_result(path)
        if "t" not in df.columns:
            continue
        series[row["attribute"]] = pd.to_numeric(df["t"], errors="coerce")
    return pd.DataFrame(series).sort_index()


def write_gmt_from_limma_results(
    path: Path,
    audit: pd.DataFrame,
    direction: str,
    top_n: int,
    classic_gmt: bool,
    up_down_from_limma_voom_func,
) -> None:
    """
    Write GMTs using Ma'ayan Lab's notebook helper:

        up_down_from_limma_voom(expr, top_n=600)

    That helper sorts the full limma-voom result table by P.Value, keeps the
    top_n most significant genes total, and then splits that subset into:
      up   = logFC > 0
      down = logFC < 0

    This is why a legacy "Up" set may contain ~250 genes even though top_n is
    600: 600 is the total significant-gene pool before direction splitting, not
    the number of genes forced into each direction.
    """
    assert direction in {"up", "down"}
    eprint(f"[write] {path}")

    with open(path, "w", encoding="utf-8") as fw:
        for _, row in audit[audit["status"] == "ok"].iterrows():
            result_path = Path(row["result_file"])
            if not result_path.exists():
                continue

            df = read_limma_result(result_path)
            geneset = up_down_from_limma_voom_func(df, top_n=top_n)
            genes = geneset.up if direction == "up" else geneset.down
            set_name = f"{row['attribute']} {'Up' if direction == 'up' else 'Down'}"

            if not genes:
                continue

            genes = list(map(str, genes))
            if classic_gmt:
                fw.write(set_name + "\tNA\t" + "\t".join(genes) + "\n")
            else:
                fw.write(set_name + "\t" + " ".join(genes) + "\n")


def write_gmt_top_per_direction_from_limma_results(
    path: Path,
    audit: pd.DataFrame,
    direction: str,
    top_n: int,
    classic_gmt: bool,
    sort_by: str,
) -> None:
    """
    Legacy-style GMT writer: choose the top N genes separately for each
    direction.

    Up:
      logFC > 0, sorted by selected statistic, keep top_n
    Down:
      logFC < 0, sorted by selected statistic, keep top_n

    This differs from up_down_from_limma_voom, where top_n is applied before
    splitting into up/down. Use this mode if reproducing legacy exported GMTs
    that appear capped to a fixed number of genes per direction, e.g. 250 Up
    genes and 250 Down genes.
    """
    assert direction in {"up", "down"}
    if sort_by not in {"P.Value", "adj.P.Val", "t", "logFC_abs"}:
        raise ValueError(f"Unsupported --gmt-sort-by value: {sort_by}")

    eprint(f"[write] {path}")

    with open(path, "w", encoding="utf-8") as fw:
        for _, row in audit[audit["status"] == "ok"].iterrows():
            result_path = Path(row["result_file"])
            if not result_path.exists():
                continue

            df = read_limma_result(result_path).copy()
            if "logFC" not in df.columns:
                continue

            df["logFC"] = pd.to_numeric(df["logFC"], errors="coerce")
            df = df.dropna(subset=["logFC"])

            if direction == "up":
                sub = df[df["logFC"] > 0].copy()
                set_name = f"{row['attribute']} Up"
            else:
                sub = df[df["logFC"] < 0].copy()
                set_name = f"{row['attribute']} Down"

            if sub.empty:
                continue

            if sort_by == "logFC_abs":
                sub["_sort"] = sub["logFC"].abs()
                sub = sub.sort_values("_sort", ascending=False)
            elif sort_by == "t":
                if "t" not in sub.columns:
                    continue
                sub["t"] = pd.to_numeric(sub["t"], errors="coerce")
                # For up, largest positive t first. For down, most negative t first.
                sub = sub.sort_values("t", ascending=(direction == "down"))
            else:
                if sort_by not in sub.columns:
                    continue
                sub[sort_by] = pd.to_numeric(sub[sort_by], errors="coerce")
                sub = sub.sort_values(sort_by, ascending=True)

            genes = sub.head(top_n).index.astype(str).tolist()
            if not genes:
                continue

            if classic_gmt:
                fw.write(set_name + "\tNA\t" + "\t".join(genes) + "\n")
            else:
                fw.write(set_name + "\t" + " ".join(genes) + "\n")


def write_gmt_notebook_adj_pval_from_limma_results(
    path: Path,
    audit: pd.DataFrame,
    direction: str,
    top_n: int,
    classic_gmt: bool,
    adj_pval_cutoff: float,
) -> None:
    """
    Notebook postprocessing mode:
      sigframe = sigframe[sigframe['adj.P.Val'] < 0.05]
      sigframe['Threshold'] = 1 if logFC > 0 else -1
      sort by adj.P.Val
      groupby(['Aging Signature', 'Threshold']).head(250)

    This writer applies that logic per comparison/direction.
    """
    assert direction in {"up", "down"}
    eprint(f"[write] {path}")

    with open(path, "w", encoding="utf-8") as fw:
        for _, row in audit[audit["status"] == "ok"].iterrows():
            result_path = Path(row["result_file"])
            if not result_path.exists():
                continue

            df = read_limma_result(result_path).copy()
            needed = {"logFC", "adj.P.Val"}
            if not needed.issubset(df.columns):
                continue

            df["logFC"] = pd.to_numeric(df["logFC"], errors="coerce")
            df["adj.P.Val"] = pd.to_numeric(df["adj.P.Val"], errors="coerce")
            df = df.dropna(subset=["logFC", "adj.P.Val"])
            df = df[df["adj.P.Val"] < adj_pval_cutoff].copy()

            if direction == "up":
                sub = df[df["logFC"] > 0].sort_values("adj.P.Val", ascending=True)
                set_name = f"{row['attribute']} Up"
            else:
                sub = df[df["logFC"] < 0].sort_values("adj.P.Val", ascending=True)
                set_name = f"{row['attribute']} Down"

            genes = sub.head(top_n).index.astype(str).tolist()
            if not genes:
                continue

            if classic_gmt:
                fw.write(set_name + "\tNA\t" + "\t".join(genes) + "\n")
            else:
                fw.write(set_name + "\t" + " ".join(genes) + "\n")


def write_attribute_metadata(path: Path, audit: pd.DataFrame) -> None:
    rows = []
    for _, row in audit[audit["status"] == "ok"].iterrows():
        rows.append(
            {
                "attribute": row["attribute"],
                "resource": "GTEx",
                "dataset": "GTEx Tissue-Specific Aging Signatures",
                "tissue": row["tissue"],
                "background_age": REFERENCE_AGE,
                "sample_age": row["age_group"],
                "description": (
                    'aging signature described by "GTEx [Tissue] '
                    '[Background Age] vs [Sample Age]"'
                ),
            }
        )
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)


# ---------------------------------------------------------------------------
# Notebook cell: CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run a standalone GTEx Tissue-Specific Aging Signatures limma-voom "
            "analysis equivalent to GTExAgingSignatures.ipynb."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument(
        "--expression-gct",
        required=True,
        type=Path,
        help=(
            "GTEx V8 raw gene reads GCT. Expected filename: "
            "GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz"
        ),
    )
    p.add_argument(
        "--sample-attributes",
        required=True,
        type=Path,
        help="GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt",
    )
    p.add_argument(
        "--subject-phenotypes",
        required=True,
        type=Path,
        help="GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt",
    )
    p.add_argument(
        "--human-gene-info",
        required=True,
        type=Path,
        help=(
            "Notebook human_gene_info file. Expected NCBI/Harmonizome table "
            "with columns including Symbol, Synonyms, and dbXrefs."
        ),
    )
    p.add_argument(
        "--output-dir",
        default=Path("gtex_aging_outputs"),
        type=Path,
        help="Directory where all outputs are written.",
    )

    p.add_argument(
        "--tissues",
        nargs="+",
        default=None,
        help="Optional compact tissue labels to run, e.g. Brain BloodVessel AdiposeTissue.",
    )
    p.add_argument(
        "--ages",
        nargs="+",
        choices=AGE_ORDER,
        default=["30-39", "40-49", "50-59", "60-69", "70-79"],
        help="Age groups to compare against 20-29.",
    )
    p.add_argument(
        "--random-state",
        type=int,
        default=1,
        help="Random seed used for notebook-style balanced subsampling.",
    )
    p.add_argument(
        "--min-samples-per-group",
        type=int,
        default=3,
        help="Minimum balanced sample count required in each group.",
    )

    p.add_argument(
        "--filter-mode",
        choices=["tissue", "none"],
        default="tissue",
        help=(
            "Gene filtering mode before limma-voom. tissue matches the current "
            "notebook interpretation by applying maayanlab_bioinformatics "
            "filter_by_expr once per tissue. none skips this prefilter, useful "
            "for testing legacy outputs where expected genes are removed by "
            "the current filter_by_expr implementation."
        ),
    )
    p.add_argument(
        "--write-filter-audit",
        action="store_true",
        help="Write per-tissue gene lists before/after filter_by_expr for debugging.",
    )
    p.add_argument(
        "--limma-filter-genes",
        action="store_true",
        help=(
            "Also ask limma_voom_differential_expression to filter genes inside R. "
            "Default is false because this script already applies notebook-level "
            "filter_by_expr before limma-voom."
        ),
    )
    p.add_argument(
        "--limma-voom-design",
        action="store_true",
        help="Pass voom_design=True to the Ma'ayan limma-voom helper.",
    )
    p.add_argument(
        "--drop-unmapped-genes",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "--allow-non-reads-filename",
        action="store_true",
        help="Do not fail if --expression-gct filename does not contain gene_reads.gct.",
    )

    p.add_argument(
        "--top-n",
        type=int,
        default=250,
        help=(
            "Gene-count parameter for GMT output. In notebook-adj-pval and "
            "top-per-direction modes, this is genes kept separately per "
            "direction. In maayan-helper mode, this is total genes before "
            "up/down splitting."
        ),
    )
    p.add_argument(
        "--gmt-mode",
        choices=["notebook-adj-pval", "maayan-helper", "top-per-direction"],
        default="notebook-adj-pval",
        help=(
            "GMT extraction mode. notebook-adj-pval matches the notebook's "
            "adj.P.Val < cutoff, sort by adj.P.Val, top N per direction. "
            "maayan-helper uses up_down_from_limma_voom(df, top_n). "
            "top-per-direction sorts each direction independently."
        ),
    )
    p.add_argument(
        "--gmt-sort-by",
        choices=["P.Value", "adj.P.Val", "t", "logFC_abs"],
        default="P.Value",
        help="Ranking column used only when --gmt-mode top-per-direction.",
    )
    p.add_argument(
        "--gmt-adj-pval-cutoff",
        type=float,
        default=0.05,
        help="Adjusted P-value cutoff used only in notebook-adj-pval GMT mode.",
    )
    p.add_argument(
        "--classic-gmt",
        action="store_true",
        help="Write classic 3+ column GMT instead of two-column Harmonizome/DIG style.",
    )
    p.add_argument(
        "--skip-combined-outputs",
        action="store_true",
        help="Only write per-comparison limma-voom TSVs plus audit/manifest.",
    )
    p.add_argument(
        "--chunksize",
        type=int,
        default=1000,
        help="Number of GCT gene rows to read at a time in low-memory tissue loading.",
    )
    p.add_argument(
        "--save-filtered-counts",
        action="store_true",
        help="Write filtered count matrices for each comparison. This can use substantial disk space.",
    )

    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Notebook cells: full execution
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    validate_reads_gct_name(args.expression_gct, strict=not args.allow_non_reads_filename)

    mkdirp(args.output_dir)
    mkdirp(args.output_dir / "limma_voom_results")
    mkdirp(args.output_dir / "filtered_counts")

    filter_by_expr_func, limma_voom_func, up_down_from_limma_voom_func = import_maayanlab_functions()

    sample_attr = read_table(args.sample_attributes)
    subject_pheno = read_table(args.subject_phenotypes)
    ensembl_to_symbol = read_human_gene_info_ensembl_mapping(args.human_gene_info)

    metadata = build_sample_metadata(sample_attr, subject_pheno)

    # Restrict metadata to samples present in the GCT.
    header = gct_header_columns(args.expression_gct)
    gct_samples = set(header) - {"Name", "Description"}
    metadata = metadata[metadata["SAMPID"].isin(gct_samples)].copy()

    if args.tissues:
        metadata = metadata[metadata["TISSUE"].isin(set(args.tissues))].copy()

    metadata_path = args.output_dir / "gtex_aging_sample_metadata.tsv"
    eprint(f"[write] {metadata_path}")
    metadata.to_csv(metadata_path, sep="\t", index=False)

    all_audits: list[ComparisonAudit] = []

    for tissue in sorted(metadata["TISSUE"].unique()):
        tissue_meta = metadata[metadata["TISSUE"] == tissue].copy()
        tissue_samples = tissue_meta["SAMPID"].tolist()
        eprint(f"[tissue] {tissue}; samples={len(tissue_samples):,}")

        counts = read_count_matrix_for_samples_lowmem(
            path=args.expression_gct,
            sample_ids=tissue_samples,
            ensembl_to_symbol=ensembl_to_symbol,
            chunksize=args.chunksize,
        )

        n_genes_before_tissue_filter = counts.shape[0]
        if args.write_filter_audit:
            audit_dir = args.output_dir / "filter_audit"
            mkdirp(audit_dir)
            pd.Series(counts.index.astype(str), name="gene_symbol").to_csv(
                audit_dir / f"{safe_filename(tissue)}.before_filter_by_expr.tsv",
                sep="\t",
                index=False,
            )

        if args.filter_mode == "tissue":
            counts = filter_by_expr_func(counts)
            eprint(
                f"[filter_by_expr] {tissue}; genes "
                f"{n_genes_before_tissue_filter:,} -> {counts.shape[0]:,}"
            )
        else:
            eprint(
                f"[filter_by_expr] {tissue}; skipped by --filter-mode none; "
                f"genes={counts.shape[0]:,}"
            )

        if args.write_filter_audit:
            audit_dir = args.output_dir / "filter_audit"
            pd.Series(counts.index.astype(str), name="gene_symbol").to_csv(
                audit_dir / f"{safe_filename(tissue)}.after_filter_by_expr.tsv",
                sep="\t",
                index=False,
            )

        ref_samples_all = tissue_meta.loc[
            tissue_meta["AGE_GROUP"] == REFERENCE_AGE, "SAMPID"
        ].tolist()

        for age_group in args.ages:
            if age_group == REFERENCE_AGE:
                continue

            case_samples_all = tissue_meta.loc[
                tissue_meta["AGE_GROUP"] == age_group, "SAMPID"
            ].tolist()

            audit = run_one_comparison(
                counts_gene_by_sample=counts,
                tissue=tissue,
                age_group=age_group,
                ref_samples_all=ref_samples_all,
                case_samples_all=case_samples_all,
                output_dir=args.output_dir,
                random_state=args.random_state,
                min_samples_per_group=args.min_samples_per_group,
                limma_voom_func=limma_voom_func,
                limma_filter_genes=args.limma_filter_genes,
                limma_voom_design=args.limma_voom_design,
                save_filtered_counts=args.save_filtered_counts,
            )
            all_audits.append(audit)
            if audit.status != "ok":
                eprint(f"[skip] {audit.attribute}: {audit.status}")

        del counts

    audit_df = pd.DataFrame([asdict(x) for x in all_audits])
    audit_path = args.output_dir / "gtex_aging_processing_audit.tsv"
    eprint(f"[write] {audit_path}")
    audit_df.to_csv(audit_path, sep="\t", index=False)

    if not args.skip_combined_outputs:
        t_matrix = build_t_stat_matrix(audit_df)
        if not t_matrix.empty:
            matrix_path = args.output_dir / "gene_attribute_matrix_limma_t.tsv.gz"
            eprint(f"[write] {matrix_path}")
            t_matrix.to_csv(matrix_path, sep="\t", compression="gzip")

            gene_list_path = args.output_dir / "gene_list.tsv"
            eprint(f"[write] {gene_list_path}")
            pd.Series(t_matrix.index, name="gene").to_csv(gene_list_path, sep="\t", index=False)

        if args.gmt_mode == "notebook-adj-pval":
            write_gmt_notebook_adj_pval_from_limma_results(
                args.output_dir / "gene_set_library_up.gmt",
                audit_df,
                direction="up",
                top_n=args.top_n,
                classic_gmt=args.classic_gmt,
                adj_pval_cutoff=args.gmt_adj_pval_cutoff,
            )
            write_gmt_notebook_adj_pval_from_limma_results(
                args.output_dir / "gene_set_library_dn.gmt",
                audit_df,
                direction="down",
                top_n=args.top_n,
                classic_gmt=args.classic_gmt,
                adj_pval_cutoff=args.gmt_adj_pval_cutoff,
            )
        elif args.gmt_mode == "maayan-helper":
            write_gmt_from_limma_results(
                args.output_dir / "gene_set_library_up.gmt",
                audit_df,
                direction="up",
                top_n=args.top_n,
                classic_gmt=args.classic_gmt,
                up_down_from_limma_voom_func=up_down_from_limma_voom_func,
            )
            write_gmt_from_limma_results(
                args.output_dir / "gene_set_library_dn.gmt",
                audit_df,
                direction="down",
                top_n=args.top_n,
                classic_gmt=args.classic_gmt,
                up_down_from_limma_voom_func=up_down_from_limma_voom_func,
            )
        else:
            write_gmt_top_per_direction_from_limma_results(
                args.output_dir / "gene_set_library_up.gmt",
                audit_df,
                direction="up",
                top_n=args.top_n,
                classic_gmt=args.classic_gmt,
                sort_by=args.gmt_sort_by,
            )
            write_gmt_top_per_direction_from_limma_results(
                args.output_dir / "gene_set_library_dn.gmt",
                audit_df,
                direction="down",
                top_n=args.top_n,
                classic_gmt=args.classic_gmt,
                sort_by=args.gmt_sort_by,
            )
        write_attribute_metadata(args.output_dir / "attribute_metadata.tsv", audit_df)

    manifest = {
        "script": Path(__file__).name,
        "notebook": "GTEx/Tissue-Specific Aging Signatures/GTExAgingSignatures.ipynb",
        "expression_gct": str(args.expression_gct),
        "expression_type": "GTEx V8 raw gene reads",
        "sample_attributes": str(args.sample_attributes),
        "subject_phenotypes": str(args.subject_phenotypes),
        "human_gene_info": str(args.human_gene_info),
        "output_dir": str(args.output_dir),
        "reference_age": REFERENCE_AGE,
        "ages": args.ages,
        "random_state": args.random_state,
        "min_samples_per_group": args.min_samples_per_group,
        "filter_mode": args.filter_mode,
        "chunksize": args.chunksize,
        "limma_filter_genes": args.limma_filter_genes,
        "limma_voom_design": args.limma_voom_design,
        "top_n": args.top_n,
        "gmt_mode": args.gmt_mode,
        "gmt_sort_by": args.gmt_sort_by,
        "gmt_adj_pval_cutoff": args.gmt_adj_pval_cutoff,
        "gmt_extraction": (
            "notebook_adj_pval_lt_cutoff_top_n_per_direction"
            if args.gmt_mode == "notebook-adj-pval"
            else (
                "maayanlab_bioinformatics.dge.limma_voom.up_down_from_limma_voom"
                if args.gmt_mode == "maayan-helper"
                else "top_per_direction"
            )
        ),
        "comparisons_ok": int((audit_df["status"] == "ok").sum()) if not audit_df.empty else 0,
        "comparisons_total": int(audit_df.shape[0]),
    }
    manifest_path = args.output_dir / "run_manifest.json"
    eprint(f"[write] {manifest_path}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    eprint(
        f"[done] comparisons ok={manifest['comparisons_ok']}/"
        f"{manifest['comparisons_total']}; outputs={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
