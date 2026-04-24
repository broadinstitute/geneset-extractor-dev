#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import logging
import os
import shlex
import shutil
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_gtex_harmonizome_analysis_v1")

DOWNLOADS = {
    "counts_gct_gz": "https://storage.googleapis.com/adult-gtex/bulk-gex/v8/rna-seq/GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz",
    "sample_attributes_tsv": "https://storage.googleapis.com/adult-gtex/annotations/v8/metadata-files/GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt",
    "subject_phenotypes_tsv": "https://storage.googleapis.com/adult-gtex/annotations/v8/metadata-files/GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt",
}

SMTS_TO_LEGACY = {
    "Adipose Tissue": "AdiposeTissue",
    "Adrenal Gland": "AdrenalGland",
    "Bladder": "Bladder",
    "Blood": "Blood",
    "Blood Vessel": "BloodVessel",
    "Brain": "Brain",
    "Breast": "Breast",
    "Colon": "Colon",
    "Esophagus": "Esophagus",
    "Heart": "Heart",
    "Kidney": "Kidney",
    "Liver": "Liver",
    "Lung": "Lung",
    "Muscle": "Muscle",
    "Nerve": "Nerve",
    "Ovary": "Ovary",
    "Pancreas": "Pancreas",
    "Pituitary": "Pituitary",
    "Prostate": "Prostate",
    "Minor Salivary Gland": "SalivaryGland",
    "Skin": "Skin",
    "Small Intestine": "SmallIntestine",
    "Spleen": "Spleen",
    "Stomach": "Stomach",
    "Testis": "Testis",
    "Thyroid": "Thyroid",
    "Uterus": "Uterus",
    "Vagina": "Vagina",
}

REFERENCE_AGE = "20-29"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--workflow_repo", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--dry_run", action="store_true")
    return parser.parse_args()


def configure_logging(level: str, log_path: Path | None = None) -> None:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(resolved_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def ensure_download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        LOGGER.info("download exists: %s (%d bytes)", destination, destination.stat().st_size)
        return
    LOGGER.info("downloading: %s -> %s", url, destination)
    with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    LOGGER.info("download complete: %s (%d bytes)", destination, destination.stat().st_size)


def require_existing_download_for_dry_run(path: Path, label: str) -> None:
    if not path.exists() or path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"dry-run requires existing local input for {label}: {path}"
        )


def append_command(
    command_rows: list[dict[str, object]],
    *,
    step: str,
    workdir: Path,
    cmd: list[str],
    metadata: dict[str, object] | None = None,
) -> None:
    command_one_line = shlex.join(cmd)
    command_multiline = " \\\n".join(shlex.quote(part) for part in cmd)
    row: dict[str, object] = {
        "step": step,
        "workdir": str(workdir),
        "command": command_one_line,
        "command_multiline": command_multiline,
    }
    if metadata:
        row.update(metadata)
    command_rows.append(row)


def format_pretty_example_command(cmd: list[str]) -> str:
    repo_root = Path.cwd().resolve()

    def _render_token(token: str) -> str:
        try:
            token_path = Path(token)
            if token_path.is_absolute():
                resolved = token_path.resolve()
                try:
                    return shlex.quote(str(resolved.relative_to(repo_root)))
                except ValueError:
                    return shlex.quote(str(token))
        except Exception:
            pass
        return shlex.quote(str(token))

    if not cmd:
        return ""

    first_option_index = next((index for index, token in enumerate(cmd) if token.startswith("--")), len(cmd))
    head_tokens = cmd[:first_option_index]
    tail_tokens = cmd[first_option_index:]
    lines: list[str] = []

    head_line = " ".join(_render_token(token) for token in head_tokens)
    if tail_tokens:
        lines.append(f"{head_line} \\")
    else:
        lines.append(head_line)

    index = 0
    while index < len(tail_tokens):
        token = tail_tokens[index]
        if token.startswith("--"):
            if index + 1 < len(tail_tokens) and not tail_tokens[index + 1].startswith("--"):
                line = f"  {shlex.quote(token)} {_render_token(tail_tokens[index + 1])}"
                index += 2
            else:
                line = f"  {shlex.quote(token)}"
                index += 1
        else:
            line = f"  {_render_token(token)}"
            index += 1
        if index < len(tail_tokens):
            line += " \\"
        lines.append(line)
    return "\n".join(lines)


def select_example_rows(command_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    example_rows: list[dict[str, object]] = []
    seen_steps: set[str] = set()
    for row in command_rows:
        step = str(row.get("step", ""))
        if step in seen_steps:
            continue
        seen_steps.add(step)
        example_rows.append(row)
    return example_rows


def get_tissue_matrix_generation_example(output_dir: Path, tissue_name: str = "AdiposeTissue") -> str:
    repo_root = Path.cwd().resolve()
    matrix_dir = output_dir / "prepared" / "tissue_matrices"
    metadata_dir = output_dir / "prepared" / "tissue_metadata"
    comparisons_dir = output_dir / "prepared" / "tissue_comparisons"
    counts_filename = Path(DOWNLOADS["counts_gct_gz"]).name

    def _rel(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(repo_root))
        except ValueError:
            return str(path)

    return "\n".join(
        [
            f"counts_gct_gz_path = downloads_dir / \"{counts_filename}\"",
            "matrix_dir = prepared_dir / \"tissue_matrices\"",
            "metadata_dir = prepared_dir / \"tissue_metadata\"",
            "comparisons_dir = prepared_dir / \"tissue_comparisons\"",
            "",
            "tissue_metadata_df = metadata_df[metadata_df[\"legacy_tissue\"] == \"AdiposeTissue\"].copy()",
            "tissue_metadata_df = tissue_metadata_df[[",
            "    \"sample_id\", \"subjid\", \"age_bin\", \"sex\", \"smts\", \"smtsd\", \"legacy_tissue\"",
            "]].drop_duplicates(subset=[\"sample_id\"])",
            "",
            "with gzip.open(counts_gct_gz_path, \"rt\", encoding=\"utf-8\") as handle:",
            "    version_line = handle.readline().strip()",
            "    dims_line = handle.readline().strip()",
            "    header = handle.readline().rstrip(\"\\n\").split(\"\\t\")",
            "    sample_columns = header[2:]",
            "    sample_index = {sample_id: idx for idx, sample_id in enumerate(sample_columns)}",
            "    indices = [sample_index[sample_id] for sample_id in tissue_metadata_df[\"sample_id\"] if sample_id in sample_index]",
            "    ordered_samples = [sample_columns[idx] for idx in indices]",
            "",
            f"    with open(r\"{_rel(matrix_dir / f'{tissue_name}.v1.tsv')}\", \"w\", encoding=\"utf-8\", newline=\"\") as matrix_handle:",
            "        writer = csv.writer(matrix_handle, delimiter=\"\\t\")",
            "        writer.writerow([\"Name\", \"Description\", *ordered_samples])",
            "        for raw_line in handle:",
            "            fields = raw_line.rstrip(\"\\n\").split(\"\\t\")",
            "            gene_id = fields[0]",
            "            gene_symbol = fields[1]",
            "            values = fields[2:]",
            "            selected_values = [values[idx] if idx < len(values) else \"\" for idx in indices]",
            "            writer.writerow([gene_id, gene_symbol, *selected_values])",
            "",
            f"tissue_metadata_df.to_csv(r\"{_rel(metadata_dir / f'{tissue_name}.v1.tsv')}\", sep=\"\\t\", index=False)",
            "tissue_comparisons_df = comparison_df[comparison_df[\"legacy_tissue\"] == \"AdiposeTissue\"][[",
            "    \"comparison_id\", \"comparison_kind\", \"group_column\", \"group_a\", \"group_b\"",
            "]]",
            f"tissue_comparisons_df.to_csv(r\"{_rel(comparisons_dir / f'{tissue_name}.v1.tsv')}\", sep=\"\\t\", index=False)",
        ]
    )


def write_dry_run_outputs(
    command_rows: list[dict[str, object]],
    output_dir: Path,
    title: str,
    script_explanation: str,
    step_explanations: dict[str, str] | None = None,
    notes: list[str] | None = None,
) -> Path:
    example_rows = select_example_rows(command_rows)
    report_path = output_dir / "dry_run_examples.v2.md"
    lines = [
        f"# {title}",
        "",
        f"- total_examples: {len(example_rows)}",
        "",
        script_explanation,
        "",
        "The commands below are representative examples, not the full expanded command list.",
        "Each example shows the first command of that type in the order the script would run it.",
        "Internal Python dataframe preparation and file writes are not included.",
        "",
    ]
    if notes:
        lines.extend(notes)
        lines.append("")
    lines.append("## Internal Preparation")
    lines.append("")
    lines.append("### 1. build_tissue_matrices")
    lines.append("")
    lines.append("- explanation: Internal Python step that creates the per-tissue matrix, metadata, and comparison TSV files before the external workflow commands run.")
    lines.append("- example_tissue: `AdiposeTissue`")
    lines.append("")
    lines.append("```python")
    lines.append(get_tissue_matrix_generation_example(output_dir))
    lines.append("```")
    lines.append("")
    lines.append("## Example Commands")
    lines.append("")
    for order_index, row in enumerate(example_rows, start=2):
        step = str(row["step"])
        lines.append(f"### {order_index}. {step}")
        lines.append("")
        lines.append(f"- explanation: {step_explanations.get(step, 'Representative external command from this workflow.') if step_explanations else 'Representative external command from this workflow.'}")
        lines.append(f"- workdir: `{row['workdir']}`")
        if "legacy_tissue" in row and pd.notna(row["legacy_tissue"]):
            lines.append(f"- example_tissue: `{row['legacy_tissue']}`")
        lines.append("")
        lines.append("```bash")
        lines.append(format_pretty_example_command(shlex.split(str(row["command"]))))
        lines.append("```")
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote dry-run report: %s", report_path)
    return report_path


def read_reference_tissues(reference_gmt_gz: Path) -> list[str]:
    tissues: Counter[str] = Counter()
    with gzip.open(reference_gmt_gz, "rt", encoding="utf-8") as handle:
        for line in handle:
            set_name = line.split("\t", 1)[0]
            base_name = set_name.rsplit("_", 1)[0]
            parts = base_name.split("_")
            tissue_name = "_".join(parts[1:-3])
            tissues[tissue_name] += 1
    ordered = sorted(tissues)
    LOGGER.info("reference tissues discovered: n=%d", len(ordered))
    return ordered


def load_metadata(sample_attributes_path: Path, subject_phenotypes_path: Path, reference_tissues: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample_df = pd.read_csv(sample_attributes_path, sep="\t", dtype=str)
    subject_df = pd.read_csv(subject_phenotypes_path, sep="\t", dtype=str)
    LOGGER.info("sample attributes shape: %s", sample_df.shape)
    LOGGER.info("subject phenotypes shape: %s", subject_df.shape)

    required_sample_cols = ["SAMPID", "SMTS", "SMTSD"]
    required_subject_cols = ["SUBJID", "AGE", "SEX"]
    missing_sample = [col for col in required_sample_cols if col not in sample_df.columns]
    missing_subject = [col for col in required_subject_cols if col not in subject_df.columns]
    if missing_sample:
        raise ValueError(f"sample attributes missing columns: {missing_sample}")
    if missing_subject:
        raise ValueError(f"subject phenotypes missing columns: {missing_subject}")

    sample_df = sample_df[required_sample_cols].copy()
    sample_df["SUBJID"] = sample_df["SAMPID"].map(lambda value: "-".join(str(value).split("-")[:2]))
    merged_df = sample_df.merge(subject_df[required_subject_cols], on="SUBJID", how="left")
    merged_df["legacy_tissue"] = merged_df["SMTS"].map(SMTS_TO_LEGACY)
    merged_df["age_bin"] = merged_df["AGE"]
    merged_df = merged_df[merged_df["legacy_tissue"].isin(reference_tissues)].copy()
    merged_df = merged_df[merged_df["age_bin"].notna() & (merged_df["age_bin"] != "")].copy()
    merged_df["sample_id"] = merged_df["SAMPID"]
    merged_df["sex"] = merged_df["SEX"]
    merged_df["smts"] = merged_df["SMTS"]
    merged_df["smtsd"] = merged_df["SMTSD"]
    merged_df["subjid"] = merged_df["SUBJID"]
    LOGGER.info("prepared metadata shape after tissue/age filters: %s", merged_df.shape)
    LOGGER.info("prepared metadata age counts: %s", dict(merged_df["age_bin"].value_counts().sort_index()))

    comparison_rows: list[dict[str, str]] = []
    tissue_manifest_rows: list[dict[str, str | int]] = []
    for tissue_name, tissue_df in merged_df.groupby("legacy_tissue", sort=True):
        counts = tissue_df["age_bin"].value_counts()
        tissue_manifest_rows.append(
            {
                "legacy_tissue": tissue_name,
                "n_samples": int(tissue_df.shape[0]),
                "n_subsites": int(tissue_df["smtsd"].nunique()),
                "age_counts": ",".join(f"{age}:{int(counts[age])}" for age in sorted(counts.index)),
            }
        )
        if counts.get(REFERENCE_AGE, 0) < 2:
            continue
        for age_bin in sorted(x for x in counts.index if x != REFERENCE_AGE):
            if counts.get(age_bin, 0) < 2:
                continue
            comparison_rows.append(
                {
                    "legacy_tissue": tissue_name,
                    "comparison_id": f"GTEx_{tissue_name}_{REFERENCE_AGE}_vs_{age_bin}",
                    "comparison_kind": "condition_a_vs_b",
                    "group_column": "age_bin",
                    "group_a": age_bin,
                    "group_b": REFERENCE_AGE,
                }
            )
    tissue_manifest_df = pd.DataFrame(tissue_manifest_rows).sort_values("legacy_tissue")
    comparison_df = pd.DataFrame(comparison_rows).sort_values(["legacy_tissue", "comparison_id"])
    LOGGER.info("tissue manifest shape: %s", tissue_manifest_df.shape)
    LOGGER.info("comparison manifest shape: %s", comparison_df.shape)
    return merged_df, comparison_df


def write_dataframe(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)
    LOGGER.info("wrote table: %s shape=%s", path, df.shape)


def build_tissue_matrices(
    counts_gct_gz_path: Path,
    metadata_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    prepared_dir: Path,
    dry_run: bool = False,
) -> pd.DataFrame:
    tissues_with_comparisons = set(comparison_df["legacy_tissue"].unique())
    metadata_df = metadata_df[metadata_df["legacy_tissue"].isin(tissues_with_comparisons)].copy()
    samples_by_tissue = {
        tissue_name: list(group["sample_id"].drop_duplicates())
        for tissue_name, group in metadata_df.groupby("legacy_tissue", sort=True)
    }

    matrix_dir = prepared_dir / "tissue_matrices"
    matrix_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir = prepared_dir / "tissue_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    comparisons_dir = prepared_dir / "tissue_comparisons"
    comparisons_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        manifest_rows: list[dict[str, str | int]] = []
        for tissue_name in sorted(samples_by_tissue):
            tissue_metadata_df = metadata_df[metadata_df["legacy_tissue"] == tissue_name].copy()
            tissue_metadata_df = tissue_metadata_df[
                ["sample_id", "subjid", "age_bin", "sex", "smts", "smtsd", "legacy_tissue"]
            ].drop_duplicates(subset=["sample_id"])
            manifest_rows.append(
                {
                    "legacy_tissue": tissue_name,
                    "matrix_tsv": str(matrix_dir / f"{tissue_name}.v1.tsv"),
                    "sample_metadata_tsv": str(metadata_dir / f"{tissue_name}.v1.tsv"),
                    "comparisons_tsv": str(comparisons_dir / f"{tissue_name}.v1.tsv"),
                    "n_samples": int(tissue_metadata_df.shape[0]),
                    "n_genes": 0,
                }
            )
        manifest_df = pd.DataFrame(manifest_rows).sort_values("legacy_tissue")
        LOGGER.info("prepared dry-run matrix manifest shape: %s", manifest_df.shape)
        return manifest_df

    LOGGER.info("streaming GCT into per-tissue matrices: tissues=%d", len(samples_by_tissue))
    matrix_paths: dict[str, Path] = {tissue: matrix_dir / f"{tissue}.v1.tsv" for tissue in samples_by_tissue}
    handles: dict[str, object] = {}
    writers: dict[str, csv.writer] = {}
    gene_counts: Counter[str] = Counter()

    with gzip.open(counts_gct_gz_path, "rt", encoding="utf-8") as handle:
        version_line = handle.readline().strip()
        dims_line = handle.readline().strip()
        header = handle.readline().rstrip("\n").split("\t")
        if len(header) < 3 or header[0] != "Name" or header[1] != "Description":
            raise ValueError(f"unexpected GCT header columns: {header[:5]}")
        sample_columns = header[2:]
        sample_index = {sample_id: idx for idx, sample_id in enumerate(sample_columns)}
        LOGGER.info(
            "GCT header parsed: version=%s dims=%s n_samples=%d",
            version_line,
            dims_line,
            len(sample_columns),
        )

        index_by_tissue: dict[str, list[int]] = {}
        for tissue_name, tissue_samples in samples_by_tissue.items():
            indices = [sample_index[sample_id] for sample_id in tissue_samples if sample_id in sample_index]
            ordered_samples = [sample_columns[idx] for idx in indices]
            index_by_tissue[tissue_name] = indices
            matrix_handle = matrix_paths[tissue_name].open("w", encoding="utf-8", newline="")
            handles[tissue_name] = matrix_handle
            writer = csv.writer(matrix_handle, delimiter="\t")
            writers[tissue_name] = writer
            writer.writerow(["Name", "Description", *ordered_samples])

        for row_number, raw_line in enumerate(handle, start=1):
            fields = raw_line.rstrip("\n").split("\t")
            if len(fields) < 2:
                continue
            gene_id = fields[0]
            gene_symbol = fields[1]
            values = fields[2:]
            for tissue_name, indices in index_by_tissue.items():
                selected_values = [values[idx] if idx < len(values) else "" for idx in indices]
                writers[tissue_name].writerow([gene_id, gene_symbol, *selected_values])
                gene_counts[tissue_name] += 1
            if row_number % 5000 == 0:
                LOGGER.info("streamed gene rows: n_rows=%d", row_number)

    for tissue_name, matrix_handle in handles.items():
        matrix_handle.close()

    manifest_rows: list[dict[str, str | int]] = []
    for tissue_name in sorted(samples_by_tissue):
        tissue_metadata_df = metadata_df[metadata_df["legacy_tissue"] == tissue_name].copy()
        tissue_metadata_path = metadata_dir / f"{tissue_name}.v1.tsv"
        tissue_metadata_df = tissue_metadata_df[
            ["sample_id", "subjid", "age_bin", "sex", "smts", "smtsd", "legacy_tissue"]
        ].drop_duplicates(subset=["sample_id"])
        write_dataframe(tissue_metadata_df, tissue_metadata_path)

        tissue_comparisons_df = comparison_df[comparison_df["legacy_tissue"] == tissue_name].copy()
        tissue_comparisons_path = comparisons_dir / f"{tissue_name}.v1.tsv"
        write_dataframe(
            tissue_comparisons_df[
                ["comparison_id", "comparison_kind", "group_column", "group_a", "group_b"]
            ],
            tissue_comparisons_path,
        )
        manifest_rows.append(
            {
                "legacy_tissue": tissue_name,
                "matrix_tsv": str(matrix_paths[tissue_name]),
                "sample_metadata_tsv": str(tissue_metadata_path),
                "comparisons_tsv": str(tissue_comparisons_path),
                "n_samples": int(tissue_metadata_df.shape[0]),
                "n_genes": int(gene_counts[tissue_name]),
            }
        )
    manifest_df = pd.DataFrame(manifest_rows).sort_values("legacy_tissue")
    LOGGER.info("prepared matrix manifest shape: %s", manifest_df.shape)
    return manifest_df


def run_workflow(
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
            "harmonizome",
            "--balance_seed",
            "1",
            "--backend",
            "lightweight",
            "--out_dir",
            str(tissue_out_dir),
            "--organism",
            "human",
            "--genome_build",
            "hg38",
        ]
        LOGGER.info("running rna_de_prepare for %s", tissue_name)
        if dry_run:
            if command_rows is None:
                raise ValueError("command_rows is required when dry_run=True")
            append_command(
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
        if not deg_long_path.exists():
            raise FileNotFoundError(f"expected DE output not found: {deg_long_path}")
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


def combine_workflow_outputs(workflow_manifest_df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path, Path]:
    combined_dir = output_dir / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)
    deg_frames = []
    audit_frames = []
    comparison_manifest_frames = []

    for row in workflow_manifest_df.to_dict(orient="records"):
        deg_frames.append(pd.read_csv(Path(str(row["deg_long_tsv"])), sep="\t", dtype=str))
        audit_frames.append(pd.read_csv(Path(str(row["comparison_audit_tsv"])), sep="\t", dtype=str))
        comparison_manifest_frames.append(pd.read_csv(Path(str(row["comparison_manifest_tsv"])), sep="\t", dtype=str))

    deg_combined_df = pd.concat(deg_frames, ignore_index=True)
    audit_combined_df = pd.concat(audit_frames, ignore_index=True)
    comparison_manifest_combined_df = pd.concat(comparison_manifest_frames, ignore_index=True)
    LOGGER.info("combined deg_long shape: %s", deg_combined_df.shape)
    LOGGER.info("combined comparison_audit shape: %s", audit_combined_df.shape)
    LOGGER.info("combined comparison_manifest shape: %s", comparison_manifest_combined_df.shape)

    deg_combined_path = combined_dir / "deg_long_combined.v1.tsv"
    audit_combined_path = combined_dir / "comparison_audit_combined.v1.tsv"
    comparison_manifest_combined_path = combined_dir / "comparison_manifest_combined.v1.tsv"
    write_dataframe(deg_combined_df, deg_combined_path)
    write_dataframe(audit_combined_df, audit_combined_path)
    write_dataframe(comparison_manifest_combined_df, comparison_manifest_combined_path)
    return deg_combined_path, audit_combined_path, comparison_manifest_combined_path


def run_rna_deg_multi(
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
    ]
    LOGGER.info("running rna_deg_multi on %s", deg_combined_path)
    if dry_run:
        if command_rows is None:
            raise ValueError("command_rows is required when dry_run=True")
        append_command(
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


def convert_generated_gmt_to_legacy_names(generated_gmt_path: Path, output_dir: Path) -> tuple[Path, Path]:
    output_gmt_path = output_dir / "gtex_aging_signatures_legacy_format.v1.gmt"
    output_gmt_gz_path = output_dir / "gtex_aging_signatures_legacy_format.v1.gmt.gz"
    converted_lines: list[str] = []

    with generated_gmt_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            parts = raw_line.split("\t")
            set_name = parts[0]
            genes = parts[1:]
            prefix = "rna_deg_multi__comparison="
            if not set_name.startswith(prefix):
                continue
            comparison_label = set_name[len(prefix):]
            comparison_label = comparison_label.split("__signature=", 1)[0]
            direction = None
            if "__pos__topk=" in set_name:
                direction = "Up"
            elif "__neg__topk=" in set_name:
                direction = "Down"
            elif "__topk=" in set_name:
                direction = "Up"
            if direction is None:
                continue
            legacy_name = f"{comparison_label}_{direction}"
            converted_lines.append("\t".join([legacy_name, *genes]))

    output_gmt_path.write_text("\n".join(converted_lines) + "\n", encoding="utf-8")
    with gzip.open(output_gmt_gz_path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(converted_lines) + "\n")
    LOGGER.info("legacy formatted GMT lines written: n=%d", len(converted_lines))
    return output_gmt_path, output_gmt_gz_path


def compare_to_reference(reference_gmt_gz: Path, generated_gmt_gz: Path, output_dir: Path) -> tuple[Path, Path]:
    def read_gmt_sets(path: Path) -> dict[str, list[str]]:
        sets: dict[str, list[str]] = {}
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                parts = line.rstrip("\n").split("\t", 1)
                if len(parts) != 2:
                    continue
                set_name, genes_blob = parts
                genes = [gene for gene in genes_blob.split() if gene]
                sets[set_name] = genes
        return sets

    reference_sets = read_gmt_sets(reference_gmt_gz)
    generated_sets = read_gmt_sets(generated_gmt_gz)
    shared_names = sorted(set(reference_sets) & set(generated_sets))
    missing_names = sorted(set(reference_sets) - set(generated_sets))
    extra_names = sorted(set(generated_sets) - set(reference_sets))

    summary_rows: list[dict[str, object]] = []
    for set_name in shared_names:
        reference_genes = set(reference_sets[set_name])
        generated_genes = set(generated_sets[set_name])
        union_size = len(reference_genes | generated_genes)
        jaccard = (len(reference_genes & generated_genes) / union_size) if union_size else 0.0
        summary_rows.append(
            {
                "set_name": set_name,
                "reference_n_genes": len(reference_genes),
                "generated_n_genes": len(generated_genes),
                "shared_n_genes": len(reference_genes & generated_genes),
                "jaccard": f"{jaccard:.6f}",
            }
        )
    summary_df = pd.DataFrame(
        summary_rows,
        columns=["set_name", "reference_n_genes", "generated_n_genes", "shared_n_genes", "jaccard"],
    )
    if not summary_df.empty:
        summary_df = summary_df.sort_values(["jaccard", "set_name"], ascending=[False, True])
    summary_path = output_dir / "comparison_to_reference.v1.tsv"
    write_dataframe(summary_df, summary_path)

    report_path = output_dir / "comparison_to_reference.v1.md"
    report_lines = [
        "# GTEx Aging Signature Comparison v1",
        "",
        f"- reference sets: {len(reference_sets)}",
        f"- generated sets: {len(generated_sets)}",
        f"- shared set names: {len(shared_names)}",
        f"- missing from generated: {len(missing_names)}",
        f"- extra in generated: {len(extra_names)}",
        "",
        "## Missing set names (first 20)",
        "",
    ]
    for set_name in missing_names[:20]:
        report_lines.append(f"- {set_name}")
    report_lines.extend(["", "## Extra set names (first 20)", ""])
    for set_name in extra_names[:20]:
        report_lines.append(f"- {set_name}")
    report_lines.extend(["", "## Top shared Jaccard scores (first 20)", ""])
    for _, row in summary_df.head(20).iterrows():
        report_lines.append(
            f"- {row['set_name']}: jaccard={row['jaccard']} shared={row['shared_n_genes']} "
            f"generated={row['generated_n_genes']} reference={row['reference_n_genes']}"
        )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    LOGGER.info("wrote comparison report: %s", report_path)
    return summary_path, report_path


def write_final_output_doc(output_dir: Path, generated_gmt_gz: Path, deg_combined_path: Path) -> Path:
    doc_path = output_dir / "gtex_aging_signatures_legacy_format.v1.md"
    lines = [
        "# GTEx Harmonizome Analysis Output v1",
        "",
        "- source counts: GTEx Analysis V8 RNASeQC gene reads",
        "- workflow: `geneset_extractors workflows rna_de_prepare --de_mode harmonizome --backend lightweight`",
        "- extractor: `geneset_extractors convert rna_deg_multi`",
        f"- combined DE table: `{deg_combined_path}`",
        f"- legacy-formatted GMT gzip: `{generated_gmt_gz}`",
        "",
        "The comparison IDs were emitted as `GTEx_<TISSUE>_20-29_vs_<OLDER_BIN>` while the DE fit kept `group_a=<OLDER_BIN>` and `group_b=20-29`, matching the existing aging-signature naming convention.",
        "",
    ]
    doc_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("wrote output documentation: %s", doc_path)
    return doc_path


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    configure_logging(args.log_level, output_dir / "run_gtex_harmonizome_analysis.v1.log")
    workflow_repo = Path(args.workflow_repo).resolve()
    reference_gmt_gz = Path(args.reference_gmt_gz).resolve()
    downloads_dir = output_dir / "downloads"
    prepared_dir = output_dir / "prepared"
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir.mkdir(parents=True, exist_ok=True)

    if not workflow_repo.exists():
        raise FileNotFoundError(f"workflow repo not found: {workflow_repo}")
    if not reference_gmt_gz.exists():
        raise FileNotFoundError(f"reference gmt not found: {reference_gmt_gz}")

    counts_gct_gz_path = downloads_dir / Path(DOWNLOADS["counts_gct_gz"]).name
    sample_attributes_path = downloads_dir / Path(DOWNLOADS["sample_attributes_tsv"]).name
    subject_phenotypes_path = downloads_dir / Path(DOWNLOADS["subject_phenotypes_tsv"]).name

    if args.dry_run:
        require_existing_download_for_dry_run(counts_gct_gz_path, "counts_gct_gz")
        require_existing_download_for_dry_run(sample_attributes_path, "sample_attributes_tsv")
        require_existing_download_for_dry_run(subject_phenotypes_path, "subject_phenotypes_tsv")
    else:
        ensure_download(DOWNLOADS["counts_gct_gz"], counts_gct_gz_path)
        ensure_download(DOWNLOADS["sample_attributes_tsv"], sample_attributes_path)
        ensure_download(DOWNLOADS["subject_phenotypes_tsv"], subject_phenotypes_path)

    reference_tissues = read_reference_tissues(reference_gmt_gz)
    metadata_df, comparison_df = load_metadata(sample_attributes_path, subject_phenotypes_path, reference_tissues)
    if not args.dry_run:
        write_dataframe(
            metadata_df[
                ["sample_id", "subjid", "age_bin", "sex", "smts", "smtsd", "legacy_tissue"]
            ].drop_duplicates(subset=["sample_id"]),
            prepared_dir / "sample_metadata_all.v1.tsv",
        )
        write_dataframe(comparison_df, prepared_dir / "comparison_manifest_all.v1.tsv")

    manifest_df = build_tissue_matrices(
        counts_gct_gz_path,
        metadata_df,
        comparison_df,
        prepared_dir,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        write_dataframe(manifest_df, prepared_dir / "tissue_matrix_manifest.v1.tsv")

    command_rows: list[dict[str, object]] = []

    workflow_manifest_df = run_workflow(
        manifest_df,
        workflow_repo,
        output_dir,
        args.python_executable,
        dry_run=args.dry_run,
        command_rows=command_rows,
    )
    if args.dry_run:
        run_rna_deg_multi(
            output_dir / "combined" / "deg_long_combined.v1.tsv",
            workflow_repo,
            output_dir,
            args.python_executable,
            dry_run=True,
            command_rows=command_rows,
        )
        write_dry_run_outputs(
            command_rows,
            output_dir,
            "GTEx Harmonizome Dry Run v1",
            "This workflow first runs one `rna_de_prepare` command per tissue, then runs one `rna_deg_multi` conversion after the tissue-level DE results are combined.",
            step_explanations={
                "rna_de_prepare": "Example tissue-level differential expression workflow command. The real run repeats this pattern for each tissue in the manifest.",
                "rna_deg_multi": "Example downstream conversion command that turns the combined DEG table into gene sets after the tissue workflows finish.",
            },
        )
        return
    write_dataframe(workflow_manifest_df, output_dir / "rna_de_prepare_manifest.v1.tsv")

    deg_combined_path, _audit_combined_path, _comparison_manifest_combined_path = combine_workflow_outputs(
        workflow_manifest_df,
        output_dir,
    )
    generated_gmt_path = run_rna_deg_multi(deg_combined_path, workflow_repo, output_dir, args.python_executable)
    _generated_gmt_txt_path, generated_gmt_gz_path = convert_generated_gmt_to_legacy_names(generated_gmt_path, output_dir)
    compare_to_reference(reference_gmt_gz, generated_gmt_gz_path, output_dir)
    write_final_output_doc(output_dir, generated_gmt_gz_path, deg_combined_path)


if __name__ == "__main__":
    main()
