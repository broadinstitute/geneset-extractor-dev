#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_gtex_no_harmonizome_analysis_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--workflow_repo", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--dry_run", action="store_true")
    return parser.parse_args()


def load_v1_module() -> object:
    script_path = Path(__file__).with_name("run_gtex_harmonizome_analysis.v1.py")
    spec = importlib.util.spec_from_file_location("gtex_harmonizome_analysis_v1", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def run_workflow_modern(
    manifest_df: pd.DataFrame,
    workflow_repo: Path,
    output_dir: Path,
    python_executable: str,
    dry_run: bool = False,
    command_rows: list[dict[str, object]] | None = None,
) -> pd.DataFrame:
    workflow_results_dir = output_dir / "rna_de_prepare"
    workflow_results_dir.mkdir(parents=True, exist_ok=True)
    workflow_manifest_rows: list[dict[str, str | int]] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workflow_repo / "src")

    for row in manifest_df.to_dict(orient="records"):
        tissue_name = str(row["legacy_tissue"])
        tissue_out_dir = workflow_results_dir / f"{tissue_name}.v1"
        cmd = [
            python_executable,
            "-m",
            "geneset_extractors.cli",
            "workflows",
            "rna_de_prepare",
            "--modality",
            "bulk",
            "--counts_tsv",
            str(row["matrix_tsv"]),
            "--matrix_orientation",
            "gene_by_sample",
            "--feature_id_column",
            "Name",
            "--matrix_gene_symbol_column",
            "Description",
            "--sample_metadata_tsv",
            str(row["sample_metadata_tsv"]),
            "--sample_id_column",
            "sample_id",
            "--group_column",
            "age_bin",
            "--comparisons_tsv",
            str(row["comparisons_tsv"]),
            "--covariates",
            "sex,smtsd",
            "--de_mode",
            "modern",
            "--backend",
            "lightweight",
            "--out_dir",
            str(tissue_out_dir),
            "--organism",
            "human",
            "--genome_build",
            "hg38",
        ]
        LOGGER.info("running modern rna_de_prepare for %s", tissue_name)
        if dry_run:
            if command_rows is None:
                raise ValueError("command_rows is required when dry_run=True")
            v1 = load_v1_module()
            v1.append_command(
                command_rows,
                step="rna_de_prepare",
                workdir=workflow_repo,
                cmd=cmd,
                metadata={"legacy_tissue": tissue_name},
            )
            continue
        subprocess.run(cmd, cwd=workflow_repo, env=env, check=True)
        deg_long_path = tissue_out_dir / "deg_long.tsv"
        comparison_audit_path = tissue_out_dir / "comparison_audit.tsv"
        comparison_manifest_path = tissue_out_dir / "comparison_manifest.tsv"
        deg_long_df = pd.read_csv(deg_long_path, sep="\t", dtype=str)
        audit_df = pd.read_csv(comparison_audit_path, sep="\t", dtype=str)
        comparison_manifest_df = pd.read_csv(comparison_manifest_path, sep="\t", dtype=str)
        LOGGER.info(
            "workflow output for %s: deg_long=%s comparison_audit=%s comparison_manifest=%s",
            tissue_name,
            deg_long_df.shape,
            audit_df.shape,
            comparison_manifest_df.shape,
        )
        workflow_manifest_rows.append(
            {
                "legacy_tissue": tissue_name,
                "deg_long_tsv": str(deg_long_path),
                "comparison_audit_tsv": str(comparison_audit_path),
                "comparison_manifest_tsv": str(comparison_manifest_path),
                "n_deg_rows": int(deg_long_df.shape[0]),
                "n_comparisons": int(comparison_manifest_df.shape[0]),
            }
        )
    if not workflow_manifest_rows:
        return pd.DataFrame(
            columns=[
                "legacy_tissue",
                "deg_long_tsv",
                "comparison_audit_tsv",
                "comparison_manifest_tsv",
                "n_deg_rows",
                "n_comparisons",
            ]
        )
    workflow_manifest_df = pd.DataFrame(workflow_manifest_rows).sort_values("legacy_tissue")
    LOGGER.info("workflow manifest shape: %s", workflow_manifest_df.shape)
    return workflow_manifest_df


def run_rna_deg_multi_legacy(
    deg_combined_path: Path,
    workflow_repo: Path,
    output_dir: Path,
    python_executable: str,
    dry_run: bool = False,
    command_rows: list[dict[str, object]] | None = None,
) -> Path:
    rna_deg_multi_out_dir = output_dir / "rna_deg_multi.v1"
    gmt_path = rna_deg_multi_out_dir / "genesets.gmt"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workflow_repo / "src")
    cmd = [
        python_executable,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(deg_combined_path),
        "--comparison_column",
        "comparison_id",
        "--out_dir",
        str(rna_deg_multi_out_dir),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--postprocess_mode",
        "legacy",
    ]
    LOGGER.info("running legacy rna_deg_multi on %s", deg_combined_path)
    if dry_run:
        if command_rows is None:
            raise ValueError("command_rows is required when dry_run=True")
        v1 = load_v1_module()
        v1.append_command(
            command_rows,
            step="rna_deg_multi",
            workdir=workflow_repo,
            cmd=cmd,
        )
        return gmt_path
    subprocess.run(cmd, cwd=workflow_repo, env=env, check=True)
    if not gmt_path.exists():
        raise FileNotFoundError(f"expected genesets.gmt not found: {gmt_path}")
    return gmt_path


def write_final_output_doc(output_dir: Path, generated_gmt_gz: Path, deg_combined_path: Path) -> Path:
    doc_path = output_dir / "gtex_aging_signatures_legacy_format.v1.md"
    lines = [
        "# GTEx No-Harmonizome Analysis Output v1",
        "",
        "- source counts: GTEx Analysis V8 RNASeQC gene reads",
        "- workflow: `geneset_extractors workflows rna_de_prepare --de_mode modern --backend lightweight`",
        "- extractor: `geneset_extractors convert rna_deg_multi --postprocess_mode legacy`",
        f"- combined DE table: `{deg_combined_path}`",
        f"- legacy-formatted GMT gzip: `{generated_gmt_gz}`",
        "",
        "This rerun removes the Harmonizome-specific workflow balancing preset and the Harmonizome-specific extractor postprocessing preset.",
        "",
    ]
    doc_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("wrote output documentation: %s", doc_path)
    return doc_path


def main() -> None:
    args = parse_args()
    v1 = load_v1_module()
    output_dir = Path(args.output_dir).resolve()
    v1.configure_logging(args.log_level, output_dir / "run_gtex_no_harmonizome_analysis.v1.log")
    workflow_repo = Path(args.workflow_repo).resolve()
    reference_gmt_gz = Path(args.reference_gmt_gz).resolve()
    downloads_dir = output_dir / "downloads"
    prepared_dir = output_dir / "prepared"
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir.mkdir(parents=True, exist_ok=True)

    counts_gct_gz_path = downloads_dir / Path(v1.DOWNLOADS["counts_gct_gz"]).name
    sample_attributes_path = downloads_dir / Path(v1.DOWNLOADS["sample_attributes_tsv"]).name
    subject_phenotypes_path = downloads_dir / Path(v1.DOWNLOADS["subject_phenotypes_tsv"]).name

    if args.dry_run:
        v1.require_existing_download_for_dry_run(counts_gct_gz_path, "counts_gct_gz")
        v1.require_existing_download_for_dry_run(sample_attributes_path, "sample_attributes_tsv")
        v1.require_existing_download_for_dry_run(subject_phenotypes_path, "subject_phenotypes_tsv")
    else:
        v1.ensure_download(v1.DOWNLOADS["counts_gct_gz"], counts_gct_gz_path)
        v1.ensure_download(v1.DOWNLOADS["sample_attributes_tsv"], sample_attributes_path)
        v1.ensure_download(v1.DOWNLOADS["subject_phenotypes_tsv"], subject_phenotypes_path)

    reference_tissues = v1.read_reference_tissues(reference_gmt_gz)
    metadata_df, comparison_df = v1.load_metadata(sample_attributes_path, subject_phenotypes_path, reference_tissues)
    if not args.dry_run:
        write_dataframe(
            metadata_df[
                ["sample_id", "subjid", "age_bin", "sex", "smts", "smtsd", "legacy_tissue"]
            ].drop_duplicates(subset=["sample_id"]),
            prepared_dir / "sample_metadata_all.v1.tsv",
        )
        write_dataframe(comparison_df, prepared_dir / "comparison_manifest_all.v1.tsv")

    manifest_df = v1.build_tissue_matrices(
        counts_gct_gz_path,
        metadata_df,
        comparison_df,
        prepared_dir,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        write_dataframe(manifest_df, prepared_dir / "tissue_matrix_manifest.v1.tsv")

    command_rows: list[dict[str, object]] = []
    workflow_manifest_df = run_workflow_modern(
        manifest_df,
        workflow_repo,
        output_dir,
        args.python_executable,
        dry_run=args.dry_run,
        command_rows=command_rows,
    )
    if args.dry_run:
        run_rna_deg_multi_legacy(
            output_dir / "combined" / "deg_long_combined.v1.tsv",
            workflow_repo,
            output_dir,
            args.python_executable,
            dry_run=True,
            command_rows=command_rows,
        )
        v1.write_dry_run_outputs(
            command_rows,
            output_dir,
            "GTEx No-Harmonizome Dry Run v1",
            "This workflow first runs one `rna_de_prepare` command per tissue using `--de_mode modern`, then runs one `rna_deg_multi` conversion using `--postprocess_mode legacy` after the tissue-level DE results are combined.",
            step_explanations={
                "rna_de_prepare": "Example tissue-level differential expression workflow command for the no-Harmonizome configuration. The real run repeats this pattern for each tissue in the manifest.",
                "rna_deg_multi": "Example downstream conversion command that turns the combined DEG table into gene sets with legacy postprocessing.",
            },
        )
        return
    write_dataframe(workflow_manifest_df, output_dir / "rna_de_prepare_manifest.v1.tsv")

    deg_combined_path, _audit_combined_path, _comparison_manifest_combined_path = v1.combine_workflow_outputs(
        workflow_manifest_df,
        output_dir,
    )
    generated_gmt_path = run_rna_deg_multi_legacy(deg_combined_path, workflow_repo, output_dir, args.python_executable)
    _generated_gmt_txt_path, generated_gmt_gz_path = v1.convert_generated_gmt_to_legacy_names(generated_gmt_path, output_dir)
    v1.compare_to_reference(reference_gmt_gz, generated_gmt_gz_path, output_dir)
    write_final_output_doc(output_dir, generated_gmt_gz_path, deg_combined_path)


if __name__ == "__main__":
    main()
