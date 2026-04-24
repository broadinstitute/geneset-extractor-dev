#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
import random
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


LOGGER = logging.getLogger("run_harmonizome_legacy_gtex_reproduction_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--counts_gct_gz_path", required=True)
    parser.add_argument("--sample_attributes_path", required=True)
    parser.add_argument("--subject_phenotypes_path", required=True)
    parser.add_argument("--mapping_path", required=True)
    parser.add_argument("--reference_gmt_gz", default="")
    parser.add_argument("--rscript_executable", default="Rscript")
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--prepare_only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def configure_logging(level: str, log_path: Path) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    LOGGER.info("wrote text: %s", path)


def count_tsv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def tsv_has_consistent_field_counts(path: Path) -> bool:
    expected_fields: int | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            field_count = line.count("\t") + 1
            if expected_fields is None:
                expected_fields = field_count
                continue
            if field_count != expected_fields:
                LOGGER.warning(
                    "inconsistent TSV field count path=%s line=%d expected=%d observed=%d",
                    path,
                    line_number,
                    expected_fields,
                    field_count,
                )
                return False
    return True


def processed_matrix_has_valid_gene_symbols(path: Path) -> bool:
    if not tsv_has_consistent_field_counts(path):
        return False
    try:
        gene_symbol_df = pd.read_csv(path, sep="\t", usecols=["gene_symbol"], dtype=str)
    except ValueError:
        LOGGER.warning("processed matrix missing gene_symbol column path=%s", path)
        return False
    gene_symbols = gene_symbol_df["gene_symbol"].dropna().astype(str)
    duplicate_rows = int(gene_symbols.shape[0] - gene_symbols.nunique())
    numeric_rows = int(gene_symbols.str.fullmatch(r"\d+").sum())
    if duplicate_rows:
        LOGGER.warning("processed matrix has duplicate gene_symbol rows path=%s n=%d", path, duplicate_rows)
        return False
    if numeric_rows:
        LOGGER.warning("processed matrix has numeric gene_symbol rows path=%s n=%d", path, numeric_rows)
        return False
    return True


def sanitize_tissue_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value))


def read_mapping(mapping_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with mapping_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            source_id = str(parts[0]).strip()
            approved_symbol = str(parts[1]).strip()
            if not source_id.startswith("ENSG"):
                continue
            if not approved_symbol:
                continue
            mapping[source_id.split(".")[0]] = approved_symbol
    if not mapping:
        raise ValueError(f"no Ensembl-to-symbol mappings found in {mapping_path}")
    LOGGER.info("loaded mapping rows: n=%d", len(mapping))
    return mapping


def load_metadata(sample_attributes_path: Path, subject_phenotypes_path: Path) -> pd.DataFrame:
    sample_df = pd.read_csv(sample_attributes_path, sep="\t", dtype=str)
    subject_df = pd.read_csv(subject_phenotypes_path, sep="\t", dtype=str)
    LOGGER.info("sample attributes shape=%s", sample_df.shape)
    LOGGER.info("subject phenotypes shape=%s", subject_df.shape)

    sample_df = sample_df.loc[:, ["SAMPID", "SMTS"]].copy()
    sample_df["subjid"] = sample_df["SAMPID"].map(lambda value: "-".join(str(value).split("-")[:2]))

    subject_df = subject_df.loc[:, ["SUBJID", "AGE", "SEX"]].copy()
    metadata_df = sample_df.merge(subject_df, left_on="subjid", right_on="SUBJID", how="left")
    metadata_df = metadata_df.rename(
        columns={
            "SAMPID": "sample_id",
            "SMTS": "smts",
            "AGE": "age_bin",
            "SEX": "sex",
        }
    )
    metadata_df = metadata_df.loc[metadata_df["age_bin"].notna() & metadata_df["smts"].notna()].copy()
    metadata_df["tissue_name"] = metadata_df["smts"].map(sanitize_tissue_name)
    metadata_df = metadata_df.loc[:, ["sample_id", "smts", "tissue_name", "subjid", "age_bin", "sex"]]
    metadata_df = metadata_df.drop_duplicates(subset=["sample_id"]).reset_index(drop=True)
    LOGGER.info("merged metadata shape=%s", metadata_df.shape)
    return metadata_df


def build_comparison_manifest(metadata_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rng = random.Random(1)
    for tissue_name in sorted(metadata_df["tissue_name"].unique()):
        tissue_meta = metadata_df.loc[metadata_df["tissue_name"] == tissue_name].copy()
        control_df = tissue_meta.loc[tissue_meta["age_bin"] == "20-29"].copy()
        if control_df.shape[0] < 3:
            continue
        for age_bin in sorted(tissue_meta["age_bin"].dropna().unique()):
            if age_bin == "20-29":
                continue
            case_df = tissue_meta.loc[tissue_meta["age_bin"] == age_bin].copy()
            if case_df.shape[0] < 3:
                continue
            min_samp = min(control_df.shape[0], case_df.shape[0])
            ctl_ids = sorted(rng.sample(control_df["sample_id"].tolist(), min_samp))
            pert_ids = sorted(rng.sample(case_df["sample_id"].tolist(), min_samp))
            comparison_id = f"GTEx_{tissue_name}_20-29_vs_{age_bin}"
            rows.append(
                {
                    "comparison_id": comparison_id,
                    "tissue_name": tissue_name,
                    "smts": str(tissue_meta["smts"].iloc[0]),
                    "group_a": age_bin,
                    "group_b": "20-29",
                    "n_group_a": len(pert_ids),
                    "n_group_b": len(ctl_ids),
                    "group_a_sample_ids": "|".join(pert_ids),
                    "group_b_sample_ids": "|".join(ctl_ids),
                }
            )
    comparison_df = pd.DataFrame(rows).sort_values(["tissue_name", "comparison_id"]).reset_index(drop=True)
    LOGGER.info("comparison manifest shape=%s", comparison_df.shape)
    return comparison_df


def read_gct_header(counts_gct_gz_path: Path) -> list[str]:
    with gzip.open(counts_gct_gz_path, "rt", encoding="utf-8") as handle:
        next(handle)
        next(handle)
        header = next(handle).rstrip("\n").split("\t")
    LOGGER.info("counts header columns=%d", len(header))
    return header


def compute_row_variances(matrix_chunk_df: pd.DataFrame, sample_columns: list[str]) -> pd.Series:
    numeric_df = matrix_chunk_df.loc[:, sample_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return numeric_df.var(axis=1)


def build_gene_selection_map(
    matrix_path: Path,
    mapping: dict[str, str],
    *,
    chunksize: int = 500,
) -> tuple[dict[str, str], int]:
    best_by_ensembl: dict[str, tuple[float, str]] = {}
    best_by_symbol: dict[str, tuple[float, str]] = {}
    sample_columns: list[str] | None = None
    total_kept_ensembl = 0

    for chunk_df in pd.read_csv(matrix_path, sep="\t", dtype=str, chunksize=chunksize):
        if sample_columns is None:
            sample_columns = [column for column in chunk_df.columns if column not in {"Name", "Description"}]
        chunk_df = chunk_df.copy()
        chunk_df["ensembl_gene_id"] = chunk_df["Name"].map(lambda value: str(value).split(".")[0])
        chunk_df["gene_symbol"] = chunk_df["ensembl_gene_id"].map(mapping)
        chunk_df = chunk_df.loc[chunk_df["gene_symbol"].notna()].copy()
        if chunk_df.empty:
            continue
        variances = compute_row_variances(chunk_df, sample_columns)
        chunk_df["row_variance"] = variances.to_numpy()
        for row in chunk_df.loc[:, ["Name", "ensembl_gene_id", "gene_symbol", "row_variance"]].itertuples(index=False):
            row_name = str(row.Name)
            ensembl_gene_id = str(row.ensembl_gene_id)
            gene_symbol = str(row.gene_symbol)
            row_variance = float(row.row_variance)
            current = best_by_ensembl.get(ensembl_gene_id)
            if current is None or row_variance > current[0] or (row_variance == current[0] and row_name < current[1]):
                best_by_ensembl[ensembl_gene_id] = (row_variance, row_name)
        total_kept_ensembl += chunk_df.shape[0]

    ensembl_winners = {row_name: mapping.get(row_name.split(".")[0], "") for _, row_name in best_by_ensembl.values()}
    for row_name, gene_symbol in ensembl_winners.items():
        row_variance = float(best_by_ensembl[row_name.split(".")[0]][0])
        current = best_by_symbol.get(gene_symbol)
        if current is None or row_variance > current[0] or (row_variance == current[0] and row_name < current[1]):
            best_by_symbol[gene_symbol] = (row_variance, row_name)

    selected_row_to_symbol = {row_name: gene_symbol for gene_symbol, (_, row_name) in best_by_symbol.items()}
    return selected_row_to_symbol, len(selected_row_to_symbol)


def write_selected_processed_matrix(
    matrix_path: Path,
    processed_path: Path,
    selected_row_to_symbol: dict[str, str],
    *,
    chunksize: int = 500,
) -> int:
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    if processed_path.exists():
        processed_path.unlink()
    rows_written = 0
    header_written = False
    for chunk_df in pd.read_csv(matrix_path, sep="\t", dtype=str, chunksize=chunksize):
        selected_chunk = chunk_df.loc[chunk_df["Name"].isin(selected_row_to_symbol)].copy()
        if selected_chunk.empty:
            continue
        sample_columns = [column for column in selected_chunk.columns if column not in {"Name", "Description"}]
        selected_chunk.insert(0, "gene_symbol", selected_chunk["Name"].map(selected_row_to_symbol))
        output_chunk = selected_chunk.loc[:, ["gene_symbol", *sample_columns]].copy()
        output_chunk.to_csv(
            processed_path,
            sep="\t",
            index=False,
            mode="a" if header_written else "w",
            header=not header_written,
        )
        header_written = True
        rows_written += output_chunk.shape[0]
    if rows_written and not processed_matrix_has_valid_gene_symbols(processed_path):
        raise ValueError(f"wrote invalid processed matrix: {processed_path}")
    return rows_written


def write_tissue_matrices(
    *,
    counts_gct_gz_path: Path,
    header: list[str],
    metadata_df: pd.DataFrame,
    output_dir: Path,
    resume: bool = False,
) -> pd.DataFrame:
    tissue_samples = {
        tissue_name: metadata_df.loc[metadata_df["tissue_name"] == tissue_name, "sample_id"].tolist()
        for tissue_name in sorted(metadata_df["tissue_name"].unique())
    }
    column_to_index = {column: idx for idx, column in enumerate(header)}
    matrix_dir = output_dir / "prepared" / "tissue_matrices"
    matrix_dir.mkdir(parents=True, exist_ok=True)

    handles: dict[str, object] = {}
    manifests: list[dict[str, object]] = []
    selected_indices: dict[str, list[int]] = {}
    for tissue_name, sample_ids in tissue_samples.items():
        existing_ids = [sample_id for sample_id in sample_ids if sample_id in column_to_index]
        if not existing_ids:
            continue
        selected_indices[tissue_name] = [column_to_index["Name"], column_to_index["Description"], *[column_to_index[sample_id] for sample_id in existing_ids]]
        matrix_path = matrix_dir / f"{tissue_name}.v1.tsv"
        if resume and matrix_path.exists():
            LOGGER.info("reusing existing tissue matrix=%s", matrix_path)
        else:
            handle = matrix_path.open("w", encoding="utf-8")
            handles[tissue_name] = handle
            handle.write("\t".join(["Name", "Description", *existing_ids]) + "\n")
        manifests.append(
            {
                "tissue_name": tissue_name,
                "matrix_tsv": str(matrix_path),
                "n_samples": len(existing_ids),
            }
        )

    if handles:
        LOGGER.info("writing tissue matrices: n_tissues=%d", len(handles))
        with gzip.open(counts_gct_gz_path, "rt", encoding="utf-8") as handle:
            next(handle)
            next(handle)
            next(handle)
            for line_index, raw_line in enumerate(handle, start=1):
                parts = raw_line.rstrip("\n").split("\t")
                for tissue_name, handle_out in handles.items():
                    indices = selected_indices[tissue_name]
                    handle_out.write("\t".join(parts[idx] if idx < len(parts) else "" for idx in indices) + "\n")
                if line_index % 5000 == 0:
                    LOGGER.info("streamed count rows=%d", line_index)
    else:
        LOGGER.info("reusing all existing tissue matrices; no GCT streaming required")

    for handle in handles.values():
        handle.close()
    manifest_df = pd.DataFrame(manifests).sort_values("tissue_name").reset_index(drop=True)
    LOGGER.info("tissue matrix manifest shape=%s", manifest_df.shape)
    return manifest_df


def prepare_tissue_inputs(
    *,
    matrix_manifest_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    mapping: dict[str, str],
    output_dir: Path,
    resume: bool = False,
) -> pd.DataFrame:
    prepared_rows: list[dict[str, object]] = []
    metadata_dir = output_dir / "prepared" / "tissue_metadata"
    comparison_dir = output_dir / "prepared" / "tissue_comparisons"
    processed_matrix_dir = output_dir / "prepared" / "tissue_matrices_processed"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    comparison_dir.mkdir(parents=True, exist_ok=True)
    processed_matrix_dir.mkdir(parents=True, exist_ok=True)

    for row in matrix_manifest_df.to_dict(orient="records"):
        tissue_name = str(row["tissue_name"])
        matrix_path = Path(str(row["matrix_tsv"]))
        tissue_meta = metadata_df.loc[metadata_df["tissue_name"] == tissue_name].copy().reset_index(drop=True)
        tissue_comparisons = comparison_df.loc[comparison_df["tissue_name"] == tissue_name].copy().reset_index(drop=True)
        if tissue_comparisons.empty:
            continue

        metadata_path = metadata_dir / f"{tissue_name}.v1.tsv"
        comparisons_path = comparison_dir / f"{tissue_name}.v1.tsv"
        processed_path = processed_matrix_dir / f"{tissue_name}.v1.tsv"
        can_reuse_processed = resume and processed_path.exists() and metadata_path.exists() and comparisons_path.exists()
        if can_reuse_processed and not processed_matrix_has_valid_gene_symbols(processed_path):
            LOGGER.warning("detected malformed processed tissue inputs=%s; rebuilding", tissue_name)
            can_reuse_processed = False
        if can_reuse_processed:
            existing_df = pd.read_csv(processed_path, sep="\t", nrows=5, dtype=str)
            sample_columns = [column for column in existing_df.columns if column != "gene_symbol"]
            n_rows = count_tsv_rows(processed_path)
            prepared_rows.append(
                {
                    "tissue_name": tissue_name,
                    "smts": str(tissue_meta["smts"].iloc[0]),
                    "matrix_tsv": str(processed_path),
                    "metadata_tsv": str(metadata_path),
                    "comparisons_tsv": str(comparisons_path),
                    "n_genes": n_rows,
                    "n_samples": len(sample_columns),
                    "n_comparisons": tissue_comparisons.shape[0],
                }
            )
            LOGGER.info("reusing processed tissue inputs=%s", tissue_name)
            continue

        selection_map, n_genes = build_gene_selection_map(matrix_path, mapping)
        if not selection_map:
            raise ValueError(f"no mapped genes retained for tissue={tissue_name}")
        rows_written = write_selected_processed_matrix(matrix_path, processed_path, selection_map)
        header_df = pd.read_csv(processed_path, sep="\t", nrows=1, dtype=str)
        sample_columns = [column for column in header_df.columns if column != "gene_symbol"]
        LOGGER.info(
            "processed tissue matrix=%s n_genes=%d n_samples=%d rows_written=%d",
            tissue_name,
            n_genes,
            len(sample_columns),
            rows_written,
        )

        write_dataframe(tissue_meta, metadata_path)
        write_dataframe(tissue_comparisons, comparisons_path)
        prepared_rows.append(
            {
                "tissue_name": tissue_name,
                "smts": str(tissue_meta["smts"].iloc[0]),
                "matrix_tsv": str(processed_path),
                "metadata_tsv": str(metadata_path),
                "comparisons_tsv": str(comparisons_path),
                "n_genes": rows_written,
                "n_samples": len(sample_columns),
                "n_comparisons": tissue_comparisons.shape[0],
            }
        )

    prepared_df = pd.DataFrame(prepared_rows).sort_values("tissue_name").reset_index(drop=True)
    LOGGER.info("prepared tissue input manifest shape=%s", prepared_df.shape)
    return prepared_df


def ensure_r_packages(rscript_executable: str) -> None:
    cmd = [
        rscript_executable,
        "-e",
        "cat(requireNamespace('limma', quietly=TRUE), '\\n'); cat(requireNamespace('edgeR', quietly=TRUE), '\\n')",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if values != ["TRUE", "TRUE"]:
        raise RuntimeError(
            "R packages limma and edgeR are required for full execution but are not available. "
            "Run with --prepare_only or install those packages in the active R environment."
        )


def write_r_script(path: Path) -> None:
    script = r"""
args <- commandArgs(trailingOnly=TRUE)
if (length(args) != 5) {
  stop("expected args: matrix_tsv metadata_tsv comparisons_tsv out_dir tissue_name")
}

suppressPackageStartupMessages(library(edgeR))
suppressPackageStartupMessages(library(limma))

matrix_tsv <- args[[1]]
metadata_tsv <- args[[2]]
comparisons_tsv <- args[[3]]
out_dir <- args[[4]]
tissue_name <- args[[5]]

dir.create(out_dir, recursive=TRUE, showWarnings=FALSE)

expr_df <- read.table(matrix_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)
metadata_df <- read.table(metadata_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)
comparisons_df <- read.table(comparisons_tsv, header=TRUE, sep='\t', quote='', comment.char='', check.names=FALSE)

sample_ids <- colnames(expr_df)[-1]
counts <- as.matrix(expr_df[, -1, drop=FALSE])
gene_symbols <- as.character(expr_df$gene_symbol)
row_ids <- make.unique(gene_symbols, sep="__dup")
rownames(counts) <- row_ids
gene_symbol_by_row <- setNames(gene_symbols, row_ids)
storage.mode(counts) <- 'numeric'

dge <- DGEList(counts=counts)
keep <- filterByExpr(dge)
dge <- dge[keep, , keep.lib.sizes=FALSE]
dge <- calcNormFactors(dge)
filtered_counts <- dge$counts

for (i in seq_len(nrow(comparisons_df))) {
  comparison_id <- as.character(comparisons_df$comparison_id[i])
  group_a_ids <- unlist(strsplit(as.character(comparisons_df$group_a_sample_ids[i]), "\\|", fixed=FALSE))
  group_b_ids <- unlist(strsplit(as.character(comparisons_df$group_b_sample_ids[i]), "\\|", fixed=FALSE))
  selected_ids <- c(group_b_ids, group_a_ids)
  selected_ids <- selected_ids[selected_ids %in% colnames(filtered_counts)]
  if (length(selected_ids) < 6) {
    next
  }
  counts_sub <- filtered_counts[, selected_ids, drop=FALSE]
  group <- factor(c(rep("control", length(group_b_ids)), rep("case", length(group_a_ids))), levels=c("control", "case"))
  design <- model.matrix(~ group)
  v <- voom(counts_sub, design, plot=FALSE)
  fit <- lmFit(v, design)
  fit <- eBayes(fit)
  tt <- topTable(fit, coef="groupcase", number=Inf, sort.by="none")
  tt$gene_symbol <- unname(gene_symbol_by_row[rownames(tt)])
  missing_symbols <- is.na(tt$gene_symbol) | tt$gene_symbol == ""
  if (any(missing_symbols)) {
    tt$gene_symbol[missing_symbols] <- rownames(tt)[missing_symbols]
  }
  tt$comparison_id <- comparison_id
  tt$group_a <- as.character(comparisons_df$group_a[i])
  tt$group_b <- as.character(comparisons_df$group_b[i])
  tt$n_group_a <- length(group_a_ids)
  tt$n_group_b <- length(group_b_ids)
  tt <- tt[, c("comparison_id", "gene_symbol", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B", "group_a", "group_b", "n_group_a", "n_group_b")]
  out_path <- file.path(out_dir, paste0(comparison_id, ".v1.tsv"))
  write.table(tt, file=out_path, sep='\t', row.names=FALSE, quote=FALSE)
}
"""
    write_text(script.strip() + "\n", path)


def run_limma_voom_by_tissue(
    *,
    prepared_df: pd.DataFrame,
    rscript_executable: str,
    output_dir: Path,
) -> pd.DataFrame:
    ensure_r_packages(rscript_executable)
    r_script_path = output_dir / "run_limma_voom_tissue.v1.R"
    write_r_script(r_script_path)

    tissue_out_dir = output_dir / "deg_tissue"
    tissue_out_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []
    for row in prepared_df.to_dict(orient="records"):
        tissue_name = str(row["tissue_name"])
        out_dir = tissue_out_dir / tissue_name
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            rscript_executable,
            str(r_script_path),
            str(row["matrix_tsv"]),
            str(row["metadata_tsv"]),
            str(row["comparisons_tsv"]),
            str(out_dir),
            tissue_name,
        ]
        LOGGER.info("running limma-voom tissue=%s", tissue_name)
        result = subprocess.run(cmd, capture_output=True, text=True)
        write_text(result.stdout, out_dir / "limma_voom.stdout.v1.log")
        write_text(result.stderr, out_dir / "limma_voom.stderr.v1.log")
        if result.returncode != 0:
            raise RuntimeError(f"limma-voom failed for tissue={tissue_name}")
        files = sorted(out_dir.glob("GTEx_*.v1.tsv"))
        manifest_rows.append(
            {
                "tissue_name": tissue_name,
                "deg_out_dir": str(out_dir),
                "n_deg_tables": len(files),
            }
        )
    manifest_df = pd.DataFrame(manifest_rows).sort_values("tissue_name").reset_index(drop=True)
    LOGGER.info("deg tissue manifest shape=%s", manifest_df.shape)
    return manifest_df


def combine_deg_tables(output_dir: Path) -> pd.DataFrame:
    deg_dir = output_dir / "deg_tissue"
    rows: list[pd.DataFrame] = []
    for path in sorted(deg_dir.glob("*/*.v1.tsv")):
        df = pd.read_csv(path, sep="\t", dtype=str)
        rows.append(df)
    if not rows:
        raise ValueError("no DEG tables found to combine")
    combined_df = pd.concat(rows, ignore_index=True)
    combined_df = combined_df.rename(
        columns={
            "AveExpr": "ave_expr",
            "P.Value": "pvalue",
            "adj.P.Val": "adj_p_val",
            "B": "b_stat",
        }
    )
    LOGGER.info("combined DEG shape=%s", combined_df.shape)
    return combined_df


def build_legacy_gmt(combined_deg_df: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, Path, Path]:
    sig_df = combined_deg_df.copy()
    sig_df["adj_p_val"] = pd.to_numeric(sig_df["adj_p_val"], errors="coerce")
    sig_df["logFC"] = pd.to_numeric(sig_df["logFC"], errors="coerce")
    sig_df = sig_df.loc[sig_df["adj_p_val"].notna() & sig_df["logFC"].notna()].copy()
    sig_df = sig_df.loc[sig_df["adj_p_val"] < 0.05].copy()
    sig_df["threshold"] = np.where(sig_df["logFC"] > 0, 1, -1)
    sig_df = sig_df.sort_values(["comparison_id", "threshold", "adj_p_val", "gene_symbol"], ascending=[True, True, True, True])
    sig_df = sig_df.groupby(["comparison_id", "threshold"], as_index=False, group_keys=False).head(250).reset_index(drop=True)
    LOGGER.info("postprocessed signature rows shape=%s", sig_df.shape)

    gmt_rows: list[str] = []
    manifest_rows: list[dict[str, object]] = []
    for (comparison_id, threshold), group_df in sig_df.groupby(["comparison_id", "threshold"], sort=True):
        genes = group_df["gene_symbol"].dropna().astype(str).tolist()
        if len(genes) < 5:
            continue
        direction = "Up" if int(threshold) == 1 else "Down"
        set_name = f"{comparison_id}_{direction}"
        gmt_rows.append("\t".join([set_name, *genes]))
        manifest_rows.append(
            {
                "set_name": set_name,
                "comparison_id": comparison_id,
                "direction": direction,
                "n_genes": len(genes),
            }
        )

    manifest_df = pd.DataFrame(manifest_rows).sort_values("set_name").reset_index(drop=True)
    gmt_path = output_dir / "gtex_aging_signatures_legacy_format.v1.gmt"
    gmt_gz_path = output_dir / "gtex_aging_signatures_legacy_format.v1.gmt.gz"
    write_text("\n".join(gmt_rows) + "\n", gmt_path)
    with gzip.open(gmt_gz_path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(gmt_rows) + "\n")
    LOGGER.info("wrote legacy candidate GMT sets=%d", len(manifest_rows))
    return manifest_df, gmt_path, gmt_gz_path


def read_gmt(path: Path) -> dict[str, list[str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    out: dict[str, list[str]] = {}
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            out[parts[0]] = [token for token in parts[1:] if token]
    return out


def compare_to_reference(reference_gmt_gz: Path, generated_gmt_gz: Path, output_dir: Path) -> tuple[pd.DataFrame, Path]:
    reference_sets = read_gmt(reference_gmt_gz)
    generated_sets = read_gmt(generated_gmt_gz)
    shared_names = sorted(set(reference_sets) & set(generated_sets))
    missing_names = sorted(set(reference_sets) - set(generated_sets))
    extra_names = sorted(set(generated_sets) - set(reference_sets))
    rows: list[dict[str, object]] = []
    for set_name in shared_names:
        ref_genes = set(reference_sets[set_name])
        gen_genes = set(generated_sets[set_name])
        intersection = ref_genes & gen_genes
        union = ref_genes | gen_genes
        rows.append(
            {
                "set_name": set_name,
                "reference_n_genes": len(ref_genes),
                "generated_n_genes": len(gen_genes),
                "shared_n_genes": len(intersection),
                "jaccard": (len(intersection) / len(union)) if union else 0.0,
            }
        )
    summary_df = pd.DataFrame(rows).sort_values(["jaccard", "set_name"], ascending=[False, True]).reset_index(drop=True)
    summary_path = output_dir / "comparison_to_reference.v1.tsv"
    write_dataframe(summary_df, summary_path)

    md_lines = [
        "# Harmonizome Legacy GTEx Reproduction Comparison v1",
        "",
        f"- reference sets: {len(reference_sets)}",
        f"- generated sets: {len(generated_sets)}",
        f"- shared set names: {len(shared_names)}",
        f"- missing from generated: {len(missing_names)}",
        f"- extra in generated: {len(extra_names)}",
        "",
        "## Top shared Jaccard scores",
        "",
    ]
    for _, row in summary_df.head(20).iterrows():
        md_lines.append(
            f"- {row['set_name']}: jaccard={float(row['jaccard']):.6f} shared={int(row['shared_n_genes'])} "
            f"generated={int(row['generated_n_genes'])} reference={int(row['reference_n_genes'])}"
        )
    report_path = output_dir / "comparison_to_reference.v1.md"
    write_text("\n".join(md_lines) + "\n", report_path)
    return summary_df, report_path


def write_run_summary(
    *,
    output_dir: Path,
    metadata_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    prepared_df: pd.DataFrame,
    prepare_only: bool,
    combined_deg_df: pd.DataFrame | None,
    manifest_df: pd.DataFrame | None,
) -> None:
    summary_rows = [
        {"step": "metadata", "n_rows": metadata_df.shape[0], "n_columns": metadata_df.shape[1]},
        {"step": "comparisons", "n_rows": comparison_df.shape[0], "n_columns": comparison_df.shape[1]},
        {"step": "prepared_tissues", "n_rows": prepared_df.shape[0], "n_columns": prepared_df.shape[1]},
    ]
    if combined_deg_df is not None:
        summary_rows.append({"step": "combined_deg", "n_rows": combined_deg_df.shape[0], "n_columns": combined_deg_df.shape[1]})
    if manifest_df is not None:
        summary_rows.append({"step": "gmt_manifest", "n_rows": manifest_df.shape[0], "n_columns": manifest_df.shape[1]})
    summary_df = pd.DataFrame(summary_rows)
    write_dataframe(summary_df, output_dir / "run_summary.v1.tsv")

    lines = [
        "# Harmonizome Legacy GTEx Reproduction Run Summary v1",
        "",
        f"- prepare_only: {str(bool(prepare_only)).lower()}",
        f"- samples retained: {metadata_df.shape[0]}",
        f"- comparisons retained: {comparison_df.shape[0]}",
        f"- tissues prepared: {prepared_df.shape[0]}",
    ]
    if combined_deg_df is not None:
        lines.append(f"- combined DEG rows: {combined_deg_df.shape[0]}")
    if manifest_df is not None:
        lines.append(f"- GMT sets emitted: {manifest_df.shape[0]}")
    lines.extend(
        [
            "",
            "This implementation follows the Harmonizome GTEx aging notebook structure closely, "
            "but uses a memory-safe per-tissue extraction path instead of loading the full GTEx matrix into memory at once.",
            "",
        ]
    )
    write_text("\n".join(lines) + "\n", output_dir / "run_summary.v1.md")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_harmonizome_legacy_gtex_reproduction.v1.log")

    counts_gct_gz_path = Path(args.counts_gct_gz_path).resolve()
    sample_attributes_path = Path(args.sample_attributes_path).resolve()
    subject_phenotypes_path = Path(args.subject_phenotypes_path).resolve()
    mapping_path = Path(args.mapping_path).resolve()
    reference_gmt_gz = Path(args.reference_gmt_gz).resolve() if args.reference_gmt_gz else None

    for path in [counts_gct_gz_path, sample_attributes_path, subject_phenotypes_path, mapping_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    mapping = read_mapping(mapping_path)
    metadata_df = load_metadata(sample_attributes_path, subject_phenotypes_path)
    header = read_gct_header(counts_gct_gz_path)
    metadata_df = metadata_df.loc[metadata_df["sample_id"].isin(header)].copy().reset_index(drop=True)
    LOGGER.info("metadata after counts intersection shape=%s", metadata_df.shape)
    comparison_df = build_comparison_manifest(metadata_df)

    prepared_dir = output_dir / "prepared"
    prepared_dir.mkdir(parents=True, exist_ok=True)
    write_dataframe(metadata_df, prepared_dir / "sample_metadata_all.v1.tsv")
    write_dataframe(comparison_df, prepared_dir / "comparison_manifest_all.v1.tsv")

    matrix_manifest_df = write_tissue_matrices(
        counts_gct_gz_path=counts_gct_gz_path,
        header=header,
        metadata_df=metadata_df.loc[metadata_df["tissue_name"].isin(comparison_df["tissue_name"].unique())].copy(),
        output_dir=output_dir,
        resume=args.resume,
    )
    write_dataframe(matrix_manifest_df, prepared_dir / "tissue_matrix_manifest.v1.tsv")

    prepared_df = prepare_tissue_inputs(
        matrix_manifest_df=matrix_manifest_df,
        metadata_df=metadata_df,
        comparison_df=comparison_df,
        mapping=mapping,
        output_dir=output_dir,
        resume=args.resume,
    )
    write_dataframe(prepared_df, prepared_dir / "prepared_tissue_inputs.v1.tsv")

    if args.prepare_only:
        write_run_summary(
            output_dir=output_dir,
            metadata_df=metadata_df,
            comparison_df=comparison_df,
            prepared_df=prepared_df,
            prepare_only=True,
            combined_deg_df=None,
            manifest_df=None,
        )
        return

    run_limma_voom_by_tissue(
        prepared_df=prepared_df,
        rscript_executable=args.rscript_executable,
        output_dir=output_dir,
    )
    combined_deg_df = combine_deg_tables(output_dir)
    write_dataframe(combined_deg_df, output_dir / "deg_long_combined.v1.tsv")
    manifest_df, _, gmt_gz_path = build_legacy_gmt(combined_deg_df, output_dir)
    write_dataframe(manifest_df, output_dir / "gtex_aging_signatures_legacy_format.v1.tsv")

    if reference_gmt_gz is not None and reference_gmt_gz.exists():
        compare_to_reference(reference_gmt_gz, gmt_gz_path, output_dir)

    write_run_summary(
        output_dir=output_dir,
        metadata_df=metadata_df,
        comparison_df=comparison_df,
        prepared_df=prepared_df,
        prepare_only=False,
        combined_deg_df=combined_deg_df,
        manifest_df=manifest_df,
    )


if __name__ == "__main__":
    main()
