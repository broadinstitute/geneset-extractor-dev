#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
import random
import re
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_harmonizome_legacy_gtex_reproduction_v2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--counts_gct_gz_path", required=True)
    parser.add_argument("--sample_attributes_path", required=True)
    parser.add_argument("--subject_phenotypes_path", required=True)
    parser.add_argument("--mapping_path", required=True)
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--tissue_name", default="")
    parser.add_argument("--next_pending_tissue", action="store_true")
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


def sanitize_tissue_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value))


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
            if source_id.startswith("ENSG") and approved_symbol:
                mapping[source_id.split(".")[0]] = approved_symbol
    LOGGER.info("loaded mapping rows: n=%d", len(mapping))
    return mapping


def load_metadata(sample_attributes_path: Path, subject_phenotypes_path: Path) -> pd.DataFrame:
    sample_df = pd.read_csv(sample_attributes_path, sep="\t", dtype=str)
    subject_df = pd.read_csv(subject_phenotypes_path, sep="\t", dtype=str)
    sample_df = sample_df.loc[:, ["SAMPID", "SMTS"]].copy()
    sample_df["subjid"] = sample_df["SAMPID"].map(lambda value: "-".join(str(value).split("-")[:2]))
    subject_df = subject_df.loc[:, ["SUBJID", "AGE", "SEX"]].copy()
    metadata_df = sample_df.merge(subject_df, left_on="subjid", right_on="SUBJID", how="left")
    metadata_df = metadata_df.rename(columns={"SAMPID": "sample_id", "SMTS": "smts", "AGE": "age_bin", "SEX": "sex"})
    metadata_df = metadata_df.loc[metadata_df["age_bin"].notna() & metadata_df["smts"].notna()].copy()
    metadata_df["tissue_name"] = metadata_df["smts"].map(sanitize_tissue_name)
    metadata_df = metadata_df.loc[:, ["sample_id", "smts", "tissue_name", "subjid", "age_bin", "sex"]]
    metadata_df = metadata_df.drop_duplicates(subset=["sample_id"]).reset_index(drop=True)
    LOGGER.info("metadata shape=%s", metadata_df.shape)
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
            rows.append(
                {
                    "comparison_id": f"GTEx_{tissue_name}_20-29_vs_{age_bin}",
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
        return next(handle).rstrip("\n").split("\t")


def write_tissue_matrices(
    counts_gct_gz_path: Path,
    header: list[str],
    metadata_df: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    matrix_dir = output_dir / "prepared" / "tissue_matrices"
    matrix_dir.mkdir(parents=True, exist_ok=True)
    tissue_samples = {
        tissue_name: metadata_df.loc[metadata_df["tissue_name"] == tissue_name, "sample_id"].tolist()
        for tissue_name in sorted(metadata_df["tissue_name"].unique())
    }
    column_to_index = {column: idx for idx, column in enumerate(header)}
    manifests: list[dict[str, object]] = []
    handles: dict[str, object] = {}
    selected_indices: dict[str, list[int]] = {}
    for tissue_name, sample_ids in tissue_samples.items():
        matrix_path = matrix_dir / f"{tissue_name}.v1.tsv"
        existing_ids = [sample_id for sample_id in sample_ids if sample_id in column_to_index]
        if not existing_ids:
            continue
        manifests.append({"tissue_name": tissue_name, "matrix_tsv": str(matrix_path), "n_samples": len(existing_ids)})
        if matrix_path.exists():
            continue
        selected_indices[tissue_name] = [column_to_index["Name"], column_to_index["Description"], *[column_to_index[sample_id] for sample_id in existing_ids]]
        handle = matrix_path.open("w", encoding="utf-8")
        handle.write("\t".join(["Name", "Description", *existing_ids]) + "\n")
        handles[tissue_name] = handle
    if handles:
        LOGGER.info("writing missing tissue matrices: n=%d", len(handles))
        with gzip.open(counts_gct_gz_path, "rt", encoding="utf-8") as handle:
            next(handle)
            next(handle)
            next(handle)
            for raw_line in handle:
                parts = raw_line.rstrip("\n").split("\t")
                for tissue_name, out_handle in handles.items():
                    indices = selected_indices[tissue_name]
                    out_handle.write("\t".join(parts[idx] if idx < len(parts) else "" for idx in indices) + "\n")
        for handle in handles.values():
            handle.close()
    manifest_df = pd.DataFrame(manifests).sort_values("tissue_name").reset_index(drop=True)
    LOGGER.info("tissue matrix manifest shape=%s", manifest_df.shape)
    return manifest_df


def compute_row_variances(chunk_df: pd.DataFrame, sample_columns: list[str]) -> pd.Series:
    numeric_df = chunk_df.loc[:, sample_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return numeric_df.var(axis=1)


def build_gene_selection_map(matrix_path: Path, mapping: dict[str, str], *, chunksize: int = 500) -> dict[str, str]:
    best_by_ensembl: dict[str, tuple[float, str]] = {}
    best_by_symbol: dict[str, tuple[float, str]] = {}
    sample_columns: list[str] | None = None
    for chunk_df in pd.read_csv(matrix_path, sep="\t", dtype=str, chunksize=chunksize):
        if sample_columns is None:
            sample_columns = [column for column in chunk_df.columns if column not in {"Name", "Description"}]
        chunk_df = chunk_df.copy()
        chunk_df["ensembl_gene_id"] = chunk_df["Name"].map(lambda value: str(value).split(".")[0])
        chunk_df["gene_symbol"] = chunk_df["ensembl_gene_id"].map(mapping)
        chunk_df = chunk_df.loc[chunk_df["gene_symbol"].notna()].copy()
        if chunk_df.empty:
            continue
        chunk_df["row_variance"] = compute_row_variances(chunk_df, sample_columns).to_numpy()
        for row in chunk_df.loc[:, ["Name", "ensembl_gene_id", "gene_symbol", "row_variance"]].itertuples(index=False):
            row_name = str(row.Name)
            ensembl_gene_id = str(row.ensembl_gene_id)
            gene_symbol = str(row.gene_symbol)
            row_variance = float(row.row_variance)
            current = best_by_ensembl.get(ensembl_gene_id)
            if current is None or row_variance > current[0] or (row_variance == current[0] and row_name < current[1]):
                best_by_ensembl[ensembl_gene_id] = (row_variance, row_name)
        for ensembl_gene_id, (row_variance, row_name) in list(best_by_ensembl.items()):
            gene_symbol = mapping.get(ensembl_gene_id)
            if not gene_symbol:
                continue
            current = best_by_symbol.get(gene_symbol)
            if current is None or row_variance > current[0] or (row_variance == current[0] and row_name < current[1]):
                best_by_symbol[gene_symbol] = (row_variance, row_name)
    return {row_name: gene_symbol for gene_symbol, (_, row_name) in best_by_symbol.items()}


def write_selected_processed_matrix(matrix_path: Path, processed_path: Path, selected_row_to_symbol: dict[str, str], *, chunksize: int = 500) -> tuple[int, int]:
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    if processed_path.exists():
        processed_path.unlink()
    rows_written = 0
    n_samples = 0
    header_written = False
    for chunk_df in pd.read_csv(matrix_path, sep="\t", dtype=str, chunksize=chunksize):
        selected_chunk = chunk_df.loc[chunk_df["Name"].isin(selected_row_to_symbol)].copy()
        if selected_chunk.empty:
            continue
        sample_columns = [column for column in selected_chunk.columns if column not in {"Name", "Description"}]
        n_samples = len(sample_columns)
        selected_chunk.insert(0, "gene_symbol", selected_chunk["Name"].map(selected_row_to_symbol))
        output_chunk = selected_chunk.loc[:, ["gene_symbol", *sample_columns]].copy()
        output_chunk.to_csv(processed_path, sep="\t", index=False, mode="a" if header_written else "w", header=not header_written)
        header_written = True
        rows_written += output_chunk.shape[0]
    if rows_written and not processed_matrix_has_valid_gene_symbols(processed_path):
        raise ValueError(f"wrote invalid processed matrix: {processed_path}")
    return rows_written, n_samples


def status_paths(output_dir: Path) -> tuple[Path, Path, Path]:
    return (
        output_dir / "prepared" / "prepared_tissue_status.v1.tsv",
        output_dir / "prepared" / "prepared_tissue_status.v1.md",
        output_dir / "prepared" / "prepared_tissue_inputs.v1.tsv",
    )


def initialize_tissue_status(matrix_manifest_df: pd.DataFrame, comparison_df: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    status_path, _, _ = status_paths(output_dir)
    metadata_dir = output_dir / "prepared" / "tissue_metadata"
    comparison_dir = output_dir / "prepared" / "tissue_comparisons"
    processed_dir = output_dir / "prepared" / "tissue_matrices_processed"
    if status_path.exists():
        status_df = pd.read_csv(status_path, sep="\t", dtype=str).fillna("")
    else:
        status_df = pd.DataFrame(columns=["tissue_name", "status", "processed_matrix_tsv", "metadata_tsv", "comparisons_tsv", "n_genes", "n_samples", "n_comparisons", "error_message"])
    status_by_tissue = {str(row["tissue_name"]): row for row in status_df.to_dict(orient="records")}
    rows: list[dict[str, object]] = []
    for row in matrix_manifest_df.to_dict(orient="records"):
        tissue_name = str(row["tissue_name"])
        metadata_path = metadata_dir / f"{tissue_name}.v1.tsv"
        comparisons_path = comparison_dir / f"{tissue_name}.v1.tsv"
        processed_path = processed_dir / f"{tissue_name}.v1.tsv"
        existing = status_by_tissue.get(tissue_name, {})
        if (
            processed_path.exists()
            and metadata_path.exists()
            and comparisons_path.exists()
            and processed_matrix_has_valid_gene_symbols(processed_path)
        ):
            status = "completed"
            n_genes = count_tsv_rows(processed_path)
            n_samples = max(len(pd.read_csv(processed_path, sep="\t", nrows=1).columns) - 1, 0)
        else:
            status = "pending"
            n_genes = ""
            n_samples = ""
        n_comparisons = int(comparison_df.loc[comparison_df["tissue_name"] == tissue_name].shape[0])
        rows.append(
            {
                "tissue_name": tissue_name,
                "status": status,
                "processed_matrix_tsv": str(processed_path),
                "metadata_tsv": str(metadata_path),
                "comparisons_tsv": str(comparisons_path),
                "n_genes": n_genes,
                "n_samples": n_samples,
                "n_comparisons": n_comparisons,
                "error_message": "" if status == "completed" else str(existing.get("error_message", "")),
            }
        )
    out_df = pd.DataFrame(rows).sort_values("tissue_name").reset_index(drop=True)
    return out_df


def write_status_outputs(status_df: pd.DataFrame, output_dir: Path) -> None:
    status_path, status_md_path, inputs_path = status_paths(output_dir)
    write_dataframe(status_df, status_path)
    completed_df = status_df.loc[status_df["status"] == "completed"].copy().reset_index(drop=True)
    if not completed_df.empty:
        write_dataframe(completed_df, inputs_path)
    lines = [
        "# Prepared Tissue Status v1",
        "",
        f"- completed: {int((status_df['status'] == 'completed').sum())}",
        f"- pending: {int((status_df['status'] == 'pending').sum())}",
        f"- running: {int((status_df['status'] == 'running').sum())}",
        f"- error: {int((status_df['status'] == 'error').sum())}",
        "",
    ]
    write_text("\n".join(lines) + "\n", status_md_path)


def choose_tissue(status_df: pd.DataFrame, tissue_name: str, next_pending_tissue: bool) -> str:
    if tissue_name:
        return tissue_name
    if next_pending_tissue:
        pending_df = status_df.loc[status_df["status"].isin(["pending", "error"])].sort_values("tissue_name")
        if pending_df.empty:
            return ""
        return str(pending_df.iloc[0]["tissue_name"])
    raise ValueError("provide --tissue_name or --next_pending_tissue")


def process_single_tissue(
    tissue_name: str,
    *,
    matrix_manifest_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    mapping: dict[str, str],
    output_dir: Path,
) -> dict[str, object]:
    row = matrix_manifest_df.loc[matrix_manifest_df["tissue_name"] == tissue_name]
    if row.empty:
        raise ValueError(f"unknown tissue_name={tissue_name}")
    matrix_path = Path(str(row.iloc[0]["matrix_tsv"]))
    tissue_meta = metadata_df.loc[metadata_df["tissue_name"] == tissue_name].copy().reset_index(drop=True)
    tissue_comparisons = comparison_df.loc[comparison_df["tissue_name"] == tissue_name].copy().reset_index(drop=True)
    metadata_path = output_dir / "prepared" / "tissue_metadata" / f"{tissue_name}.v1.tsv"
    comparisons_path = output_dir / "prepared" / "tissue_comparisons" / f"{tissue_name}.v1.tsv"
    processed_path = output_dir / "prepared" / "tissue_matrices_processed" / f"{tissue_name}.v1.tsv"

    selection_map = build_gene_selection_map(matrix_path, mapping)
    if not selection_map:
        raise ValueError(f"no mapped genes retained for tissue={tissue_name}")
    rows_written, n_samples = write_selected_processed_matrix(matrix_path, processed_path, selection_map)
    write_dataframe(tissue_meta, metadata_path)
    write_dataframe(tissue_comparisons, comparisons_path)
    LOGGER.info("processed tissue matrix=%s n_genes=%d n_samples=%d", tissue_name, rows_written, n_samples)
    return {
        "tissue_name": tissue_name,
        "status": "completed",
        "processed_matrix_tsv": str(processed_path),
        "metadata_tsv": str(metadata_path),
        "comparisons_tsv": str(comparisons_path),
        "n_genes": rows_written,
        "n_samples": n_samples,
        "n_comparisons": tissue_comparisons.shape[0],
        "error_message": "",
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_harmonizome_legacy_gtex_reproduction.v2.log")

    counts_gct_gz_path = Path(args.counts_gct_gz_path).resolve()
    sample_attributes_path = Path(args.sample_attributes_path).resolve()
    subject_phenotypes_path = Path(args.subject_phenotypes_path).resolve()
    mapping_path = Path(args.mapping_path).resolve()
    for path in [counts_gct_gz_path, sample_attributes_path, subject_phenotypes_path, mapping_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    mapping = read_mapping(mapping_path)
    metadata_df = load_metadata(sample_attributes_path, subject_phenotypes_path)
    header = read_gct_header(counts_gct_gz_path)
    metadata_df = metadata_df.loc[metadata_df["sample_id"].isin(header)].copy().reset_index(drop=True)
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
    )
    write_dataframe(matrix_manifest_df, prepared_dir / "tissue_matrix_manifest.v1.tsv")

    status_df = initialize_tissue_status(matrix_manifest_df, comparison_df, output_dir)
    tissue_name = choose_tissue(status_df, args.tissue_name, args.next_pending_tissue)
    if not tissue_name:
        write_status_outputs(status_df, output_dir)
        LOGGER.info("no pending tissues remain")
        return

    status_df.loc[status_df["tissue_name"] == tissue_name, ["status", "error_message"]] = ["running", ""]
    write_status_outputs(status_df, output_dir)

    try:
        result_row = process_single_tissue(
            tissue_name,
            matrix_manifest_df=matrix_manifest_df,
            metadata_df=metadata_df,
            comparison_df=comparison_df,
            mapping=mapping,
            output_dir=output_dir,
        )
        for key, value in result_row.items():
            status_df.loc[status_df["tissue_name"] == tissue_name, key] = value
    except Exception as exc:
        status_df.loc[status_df["tissue_name"] == tissue_name, "status"] = "error"
        status_df.loc[status_df["tissue_name"] == tissue_name, "error_message"] = str(exc)
        write_status_outputs(status_df, output_dir)
        raise

    write_status_outputs(status_df, output_dir)
    write_text(
        "\n".join(
            [
                "# Harmonizome Legacy GTEx Reproduction v2",
                "",
                f"- tissue processed this invocation: {tissue_name}",
                f"- completed tissues: {int((status_df['status'] == 'completed').sum())}",
                f"- pending tissues: {int((status_df['status'] == 'pending').sum())}",
                f"- error tissues: {int((status_df['status'] == 'error').sum())}",
                "",
                "This v2 runner processes exactly one tissue per invocation and updates a per-tissue status manifest.",
                "",
            ]
        ),
        output_dir / "run_summary.v2.md",
    )


if __name__ == "__main__":
    main()
