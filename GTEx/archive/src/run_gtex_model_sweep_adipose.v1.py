#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_gtex_model_sweep_adipose_v1")
ADIPOSE_TISSUE = "AdiposeTissue"
PIGEAN_NO_ENRICHMENT_TEXT = "No gene sets passed the standalone gene-list enrichment filter"
ADIPOSE_KEYWORDS = [
    "ADIPO",
    "ADIPOCYTE",
    "ADIPOSE",
    "FAT",
    "FATTY",
    "LIPID",
    "LIPOLYSIS",
    "TRIGLYCERIDE",
    "CHOLESTEROL",
    "PPAR",
    "LEPTIN",
    "INSULIN",
    "GLUCOSE",
    "THERMOGEN",
    "BROWN_FAT",
    "WHITE_FAT",
    "VISCERAL",
    "SUBCUTANEOUS",
    "METABOL",
    "OBES",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--base_model_run_plan_tsv", required=True)
    parser.add_argument("--base_workflow_run_plan_tsv", required=True)
    parser.add_argument("--workflow_repo", required=True)
    parser.add_argument("--pigean_repo", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def configure_logging(level: str, log_path: Path) -> None:
    resolved_level = getattr(logging, str(level).upper(), logging.INFO)
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


def load_module(module_name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_repo_root(output_dir: Path) -> Path:
    return output_dir.parent.parent


def resolve_moved_gtex_path(path_str: str, repo_root: Path) -> str:
    path = Path(str(path_str))
    if path.exists():
        return str(path)
    old_prefix = Path("/home/ryank/work/geneset_extractors/gtex")
    try:
        relative = path.relative_to(old_prefix)
    except ValueError:
        return str(path)
    return str(repo_root / relative)


def read_gmt(path: Path) -> list[tuple[str, list[str]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    rows: list[tuple[str, list[str]]] = []
    with opener(path, "rt", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            parts = raw_line.split("\t")
            if len(parts) < 2:
                continue
            rows.append((parts[0], [part for part in parts[1:] if part]))
    return rows


def write_gmt_gz(rows: list[tuple[str, list[str]]], gz_path: Path) -> Path:
    gz_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(gz_path, "wt", encoding="utf-8") as handle:
        for set_name, genes in rows:
            handle.write("\t".join([set_name, *genes]) + "\n")
    LOGGER.info("wrote gmt gzip: %s n_sets=%d", gz_path, len(rows))
    return gz_path


def append_command(command_rows: list[dict[str, object]], *, step: str, workdir: Path, cmd: list[str], metadata: dict[str, object] | None = None) -> None:
    row: dict[str, object] = {
        "step": step,
        "workdir": str(workdir),
        "command": shlex.join(cmd),
    }
    if metadata:
        row.update(metadata)
    command_rows.append(row)


def classify_no_enrichment(returncode: int, stdout_text: str, stderr_text: str, expected_path: Path) -> str:
    if returncode != 0:
        return "error"
    combined = "\n".join([stdout_text, stderr_text])
    if PIGEAN_NO_ENRICHMENT_TEXT in combined:
        return "no_enrichment"
    if expected_path.exists() and expected_path.stat().st_size > 0:
        return "success"
    return "no_outputs"


def normalize_gene_list(genes: list[str]) -> tuple[str, ...]:
    return tuple(gene for gene in genes if gene)


def hash_gene_list(set_name: str, genes: tuple[str, ...]) -> str:
    payload = set_name + "\n" + "\n".join(genes)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def keyword_hits(text_values: list[str]) -> list[str]:
    combined = " ".join(text_values).upper().replace("-", "_")
    hits = [keyword for keyword in ADIPOSE_KEYWORDS if keyword in combined]
    return sorted(set(hits))


def filter_adipose_rows(rows: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    filtered = [(set_name, genes) for set_name, genes in rows if set_name.startswith("GTEx_AdiposeTissue_")]
    LOGGER.info("filtered adipose rows: n=%d", len(filtered))
    return filtered


def write_markdown_for_table(path: Path, title: str, bullets: list[str], notes: list[str] | None = None) -> Path:
    lines = [f"# {title}", ""]
    for bullet in bullets:
        lines.append(f"- {bullet}")
    if notes:
        lines.extend(["", "## Notes", ""])
        for note in notes:
            lines.append(f"- {note}")
    lines.append("")
    md_path = path.with_suffix(".md")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("wrote markdown: %s", md_path)
    return md_path


def run_command_logged(*, step_name: str, cmd: list[str], cwd: Path, env: dict[str, str], stdout_path: Path, stderr_path: Path) -> tuple[int, str, str]:
    LOGGER.info("running step=%s cwd=%s", step_name, cwd)
    LOGGER.info("command:\n%s", " \\\n".join(shlex.quote(part) for part in cmd))
    proc = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    stdout_text = proc.stdout or ""
    stderr_text = proc.stderr or ""
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    LOGGER.info("completed step=%s returncode=%d", step_name, proc.returncode)
    return proc.returncode, stdout_text, stderr_text


def build_tissue_row(repo_root: Path) -> dict[str, str]:
    manifest_path = repo_root / "outputs" / "gtex_no_harmonizome_analysis_v1" / "prepared" / "tissue_matrix_manifest.v1.tsv"
    manifest_df = pd.read_csv(manifest_path, sep="\t", dtype=str)
    adipose_df = manifest_df.loc[manifest_df["legacy_tissue"] == ADIPOSE_TISSUE]
    if adipose_df.empty:
        raise ValueError(f"legacy_tissue not found in manifest: {ADIPOSE_TISSUE}")
    row = {key: str(value) for key, value in adipose_df.iloc[0].to_dict().items()}
    for key in ["matrix_tsv", "sample_metadata_tsv", "comparisons_tsv"]:
        row[key] = resolve_moved_gtex_path(row[key], repo_root)
    return row


def write_reference_subset(reference_gmt_gz: Path, output_dir: Path) -> Path:
    adipose_rows = filter_adipose_rows(read_gmt(reference_gmt_gz))
    subset_path = output_dir / "reference_adipose_only.v1.gmt.gz"
    write_gmt_gz(adipose_rows, subset_path)
    write_markdown_for_table(
        subset_path,
        "Reference Adipose GMT v1",
        bullets=[
            f"source_gmt_gz: `{reference_gmt_gz}`",
            f"tissue_prefix: `GTEx_{ADIPOSE_TISSUE}_`",
            f"adipose_set_count: {len(adipose_rows)}",
        ],
    )
    return subset_path


def run_adipose_workflow(
    *,
    workflow_row: pd.Series,
    tissue_row: dict[str, str],
    workflow_repo: Path,
    python_executable: str,
    output_dir: Path,
    repo_root: Path,
    resume: bool,
    command_rows: list[dict[str, object]],
) -> dict[str, object]:
    workflow_name = str(workflow_row["workflow_name"])
    workflow_slug = str(workflow_row["workflow_name"]).replace("=", "_").replace(",", "_").replace("/", "_")
    workflow_dir = output_dir / "workflow_runs" / workflow_slug
    tissue_out_dir = workflow_dir / "rna_de_prepare" / f"{ADIPOSE_TISSUE}.v1"
    deg_long_tsv = tissue_out_dir / "deg_long.tsv"
    comparison_audit_tsv = tissue_out_dir / "comparison_audit.tsv"
    comparison_manifest_tsv = tissue_out_dir / "comparison_manifest.tsv"

    workflow_source = str(workflow_row["workflow_source"])
    if workflow_source == "reuse_existing_gtex_noharm":
        base_dir = repo_root / "outputs" / "gtex_no_harmonizome_analysis_v1" / "rna_de_prepare" / f"{ADIPOSE_TISSUE}.v1"
        return {
            "workflow_name": workflow_name,
            "workflow_source": workflow_source,
            "workflow_dir": str(base_dir.parent.parent),
            "deg_long_tsv": str(base_dir / "deg_long.tsv"),
            "comparison_audit_tsv": str(base_dir / "comparison_audit.tsv"),
            "comparison_manifest_tsv": str(base_dir / "comparison_manifest.tsv"),
            "status": "reused_existing",
        }
    if workflow_source == "reuse_existing_gtex_harm":
        base_dir = repo_root / "outputs" / "gtex_harmonizome_analysis_v1" / "rna_de_prepare" / f"{ADIPOSE_TISSUE}.v1"
        return {
            "workflow_name": workflow_name,
            "workflow_source": workflow_source,
            "workflow_dir": str(base_dir.parent.parent),
            "deg_long_tsv": str(base_dir / "deg_long.tsv"),
            "comparison_audit_tsv": str(base_dir / "comparison_audit.tsv"),
            "comparison_manifest_tsv": str(base_dir / "comparison_manifest.tsv"),
            "status": "reused_existing",
        }

    cmd = [
        python_executable,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "rna_de_prepare",
        "--modality",
        "bulk",
        "--counts_tsv",
        str(tissue_row["matrix_tsv"]),
        "--matrix_orientation",
        "gene_by_sample",
        "--feature_id_column",
        "Name",
        "--matrix_gene_symbol_column",
        "Description",
        "--sample_metadata_tsv",
        str(tissue_row["sample_metadata_tsv"]),
        "--sample_id_column",
        "sample_id",
        "--group_column",
        "age_bin",
        "--comparisons_tsv",
        str(tissue_row["comparisons_tsv"]),
        "--de_mode",
        str(workflow_row["workflow_de_mode"]),
        "--backend",
        str(workflow_row["workflow_backend"]),
        "--gene_filter_scope",
        str(workflow_row["workflow_gene_filter_scope"]),
        "--balance_groups",
        str(workflow_row["workflow_balance_groups"]),
        "--balance_seed",
        str(workflow_row["workflow_balance_seed"]),
        "--out_dir",
        str(tissue_out_dir),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
    ]
    covariates = str(workflow_row["workflow_covariates"]).strip()
    if covariates and covariates.lower() != "nan":
        cmd.extend(["--covariates", covariates])
    append_command(
        command_rows,
        step="rna_de_prepare",
        workdir=workflow_repo,
        cmd=cmd,
        metadata={"workflow_name": workflow_name, "legacy_tissue": ADIPOSE_TISSUE},
    )

    if not (resume and deg_long_tsv.exists() and comparison_audit_tsv.exists() and comparison_manifest_tsv.exists()):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(workflow_repo / "src")
        r_libs_user = repo_root / "outputs" / "r_libs_4.5"
        if r_libs_user.exists():
            env["R_LIBS_USER"] = str(r_libs_user)
        stdout_path = tissue_out_dir / "rna_de_prepare.stdout.v1.log"
        stderr_path = tissue_out_dir / "rna_de_prepare.stderr.v1.log"
        returncode, _stdout_text, stderr_text = run_command_logged(
            step_name="rna_de_prepare",
            cmd=cmd,
            cwd=workflow_repo,
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if returncode != 0:
            raise RuntimeError(f"workflow failed for {workflow_name} tissue={ADIPOSE_TISSUE}: {stderr_text[:500]}")

    return {
        "workflow_name": workflow_name,
        "workflow_source": workflow_source,
        "workflow_dir": str(workflow_dir),
        "deg_long_tsv": str(deg_long_tsv),
        "comparison_audit_tsv": str(comparison_audit_tsv),
        "comparison_manifest_tsv": str(comparison_manifest_tsv),
        "status": "completed",
    }


def build_model_cmd(row: pd.Series, python_executable: str, deg_long_tsv: Path, model_dir: Path) -> list[str]:
    cmd = [
        python_executable,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(deg_long_tsv),
        "--comparison_column",
        "comparison_id",
        "--out_dir",
        str(model_dir / "rna_deg_multi.v1"),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--postprocess_mode",
        str(row["extractor_postprocess_mode"]),
        "--score_mode",
        str(row["extractor_score_mode"]),
        "--select",
        str(row["extractor_select"]),
        "--top_k",
        str(row["extractor_top_k"]),
        "--gmt_source",
        str(row["extractor_gmt_source"]),
        "--gmt_topk_list",
        str(row["extractor_gmt_topk_list"]),
        "--gmt_min_genes",
        str(row["extractor_gmt_min_genes"]),
        "--gmt_max_genes",
        str(row["extractor_gmt_max_genes"]),
    ]
    if str(row["extractor_disable_default_excludes"]).lower() == "true":
        cmd.append("--disable_default_excludes")
    if str(row["extractor_gmt_biotype_allowlist"]).strip() and str(row["extractor_gmt_biotype_allowlist"]).lower() != "nan":
        cmd.extend(["--gmt_biotype_allowlist", str(row["extractor_gmt_biotype_allowlist"])])
    if str(row["extractor_padj_max"]).strip() and str(row["extractor_padj_max"]).lower() != "nan":
        cmd.extend(["--padj_max", str(row["extractor_padj_max"])])
    if str(row["extractor_pvalue_max"]).strip() and str(row["extractor_pvalue_max"]).lower() != "nan":
        cmd.extend(["--pvalue_max", str(row["extractor_pvalue_max"])])
    if str(row["extractor_min_abs_logfc"]).strip() and str(row["extractor_min_abs_logfc"]).lower() != "nan":
        cmd.extend(["--min_abs_logfc", str(row["extractor_min_abs_logfc"])])
    return cmd


def run_model(
    *,
    model_row: pd.Series,
    workflow_output_by_name: dict[str, dict[str, object]],
    workflow_repo: Path,
    python_executable: str,
    output_dir: Path,
    reference_adipose_gmt_gz: Path,
    harmonizome_module: object,
    resume: bool,
    command_rows: list[dict[str, object]],
) -> dict[str, object]:
    model_name = str(model_row["model_name"])
    model_dir = output_dir / "models" / model_name
    model_dir.mkdir(parents=True, exist_ok=True)
    deg_long_tsv = Path(str(workflow_output_by_name[str(model_row["workflow_name"])]["deg_long_tsv"]))
    generated_gmt_tsv = model_dir / "rna_deg_multi.v1" / "genesets.gmt"
    legacy_gmt_gz = model_dir / "gtex_aging_signatures_legacy_format.v1.gmt.gz"
    adipose_gmt_gz = model_dir / f"{model_name}.adipose_only.v1.gmt.gz"
    comparison_md = model_dir / "comparison_to_reference.v1.md"

    cmd = build_model_cmd(model_row, python_executable, deg_long_tsv, model_dir)
    append_command(command_rows, step="rna_deg_multi", workdir=workflow_repo, cmd=cmd, metadata={"model_name": model_name})

    if not (resume and adipose_gmt_gz.exists() and comparison_md.exists()):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(workflow_repo / "src")
        stdout_path = model_dir / "rna_deg_multi.stdout.v1.log"
        stderr_path = model_dir / "rna_deg_multi.stderr.v1.log"
        returncode, _stdout_text, stderr_text = run_command_logged(
            step_name="rna_deg_multi",
            cmd=cmd,
            cwd=workflow_repo,
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        if returncode != 0:
            raise RuntimeError(f"model failed for {model_name}: {stderr_text[:500]}")
        if not generated_gmt_tsv.exists():
            raise FileNotFoundError(generated_gmt_tsv)
        _legacy_gmt_path, converted_gmt_gz = harmonizome_module.convert_generated_gmt_to_legacy_names(generated_gmt_tsv, model_dir)
        legacy_gmt_gz = converted_gmt_gz
        adipose_rows = filter_adipose_rows(read_gmt(legacy_gmt_gz))
        write_gmt_gz(adipose_rows, adipose_gmt_gz)
        harmonizome_module.compare_to_reference(reference_adipose_gmt_gz, adipose_gmt_gz, model_dir)
        write_text(shlex.join(cmd) + "\n", model_dir / "extractor_command.v1.sh")

    adipose_rows = filter_adipose_rows(read_gmt(adipose_gmt_gz))
    return {
        "model_name": model_name,
        "workflow_name": str(model_row["workflow_name"]),
        "model_dir": str(model_dir),
        "deg_long_tsv": str(deg_long_tsv),
        "adipose_gmt_gz": str(adipose_gmt_gz),
        "n_adipose_sets": len(adipose_rows),
        "n_unique_genes_union": len(set(gene for _set_name, genes in adipose_rows for gene in genes)),
    }


def build_canonical_outputs(model_outputs_df: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    canonical_rows: list[dict[str, object]] = []
    canonical_gmt_rows: list[tuple[str, list[str]]] = []
    model_redundancy_rows: list[dict[str, object]] = []
    seen: dict[tuple[str, tuple[str, ...]], dict[str, object]] = {}

    for _, row in model_outputs_df.iterrows():
        model_name = str(row["model_name"])
        gmt_path = Path(str(row["adipose_gmt_gz"]))
        model_set_count = 0
        model_unique_count = 0
        model_collapsed_count = 0
        for set_name, genes in read_gmt(gmt_path):
            model_set_count += 1
            normalized_genes = normalize_gene_list(genes)
            key = (set_name, normalized_genes)
            if key not in seen:
                representative_model_name = model_name
                canonical_set_name = f"{set_name}_{representative_model_name}"
                record = {
                    "base_set_name": set_name,
                    "canonical_set_name": canonical_set_name,
                    "representative_model_name": representative_model_name,
                    "collapsed_model_names": [model_name],
                    "n_models_collapsed": 1,
                    "n_genes": len(normalized_genes),
                    "gene_hash": hash_gene_list(set_name, normalized_genes),
                    "genes": list(normalized_genes),
                }
                seen[key] = record
                canonical_gmt_rows.append((canonical_set_name, list(normalized_genes)))
                model_unique_count += 1
            else:
                seen[key]["collapsed_model_names"].append(model_name)
                seen[key]["n_models_collapsed"] = len(seen[key]["collapsed_model_names"])
                model_collapsed_count += 1
        model_redundancy_rows.append(
            {
                "model_name": model_name,
                "n_original_sets": model_set_count,
                "n_unique_sets_retained": model_unique_count,
                "n_sets_collapsed_away": model_collapsed_count,
            }
        )

    for record in seen.values():
        canonical_rows.append(
            {
                "canonical_set_name": record["canonical_set_name"],
                "base_set_name": record["base_set_name"],
                "representative_model_name": record["representative_model_name"],
                "collapsed_model_names": ",".join(record["collapsed_model_names"]),
                "n_models_collapsed": record["n_models_collapsed"],
                "n_genes": record["n_genes"],
                "gene_hash": record["gene_hash"],
            }
        )

    canonical_df = pd.DataFrame(canonical_rows).sort_values(["base_set_name", "canonical_set_name"]).reset_index(drop=True)
    model_redundancy_df = pd.DataFrame(model_redundancy_rows).sort_values("model_name").reset_index(drop=True)
    canonical_gmt_gz = output_dir / "canonical_adipose_gene_sets.v1.gmt.gz"
    write_gmt_gz(canonical_gmt_rows, canonical_gmt_gz)
    return canonical_df, model_redundancy_df, canonical_gmt_gz


def run_pigean_eaggl_on_canonical_sets(
    *,
    canonical_df: pd.DataFrame,
    canonical_gmt_gz: Path,
    output_dir: Path,
    pigean_repo: Path,
    python_executable: str,
    command_rows: list[dict[str, object]],
) -> pd.DataFrame:
    bundle_data_dir = pigean_repo / "bundles" / "model_small-2026.02.22" / "data"
    x_in_path = bundle_data_dir / "gene_set_list_msigdb_nohp.txt"
    gene_map_path = bundle_data_dir / "portal_gencode.gene.map"
    gene_loc_path = bundle_data_dir / "NCBI37.3.plink.gene.loc"
    required_paths = [x_in_path, gene_map_path, gene_loc_path]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise FileNotFoundError("missing bundled PIGEAN inputs: " + ", ".join(missing_paths))

    gene_map = {set_name: genes for set_name, genes in read_gmt(canonical_gmt_gz)}
    env = os.environ.copy()
    src_root = str(pigean_repo / "src")
    env["PYTHONPATH"] = src_root if not env.get("PYTHONPATH") else src_root + os.pathsep + env["PYTHONPATH"]
    env["PYTHONHASHSEED"] = "0"
    rows: list[dict[str, object]] = []

    for _, row in canonical_df.iterrows():
        canonical_set_name = str(row["canonical_set_name"])
        genes = gene_map[canonical_set_name]
        set_output_dir = output_dir / "pigean_eaggl" / canonical_set_name
        set_output_dir.mkdir(parents=True, exist_ok=True)
        gene_list_path = set_output_dir / "input_gene_list.v1.txt"
        gene_list_path.write_text("\n".join(genes) + "\n", encoding="utf-8")

        pigean_gene_stats = set_output_dir / "pigean.gene_stats.v1.tsv"
        pigean_gene_set_stats = set_output_dir / "pigean.gene_set_stats.v1.tsv"
        pigean_params = set_output_dir / "pigean.params.v1.tsv"
        pigean_bundle = set_output_dir / "pigean_to_eaggl.v1.tar.gz"
        pigean_stdout = set_output_dir / "pigean.stdout.v1.log"
        pigean_stderr = set_output_dir / "pigean.stderr.v1.log"
        pigean_cmd = [
            python_executable,
            "-m",
            "pigean",
            "beta_tildes",
            "--X-in",
            str(x_in_path),
            "--gene-map-in",
            str(gene_map_path),
            "--gene-loc-file",
            str(gene_loc_path),
            "--gene-list-in",
            str(gene_list_path),
            "--gene-list-no-header",
            "--gene-list-id-col",
            "1",
            "--gene-list-all-in",
            str(gene_loc_path),
            "--gene-list-all-id-col",
            "6",
            "--gene-list-all-no-header",
            "--hide-opts",
            "--deterministic",
            "--min-gene-set-size",
            "1",
            "--filter-gene-set-p",
            "1",
            "--max-gene-set-read-p",
            "1",
            "--no-filter-negative",
            "--max-num-gene-sets-initial",
            "200",
            "--max-num-gene-sets-hyper",
            "200",
            "--max-num-gene-sets",
            "200",
            "--max-num-burn-in",
            "5",
            "--max-num-iter-betas",
            "20",
            "--min-num-iter-betas",
            "5",
            "--num-chains-betas",
            "2",
            "--gene-stats-out",
            str(pigean_gene_stats),
            "--gene-set-stats-out",
            str(pigean_gene_set_stats),
            "--params-out",
            str(pigean_params),
            "--eaggl-bundle-out",
            str(pigean_bundle),
        ]
        append_command(command_rows, step="pigean_beta_tildes", workdir=pigean_repo, cmd=pigean_cmd, metadata={"canonical_set_name": canonical_set_name})
        pigean_returncode, pigean_stdout_text, pigean_stderr_text = run_command_logged(
            step_name="pigean_beta_tildes",
            cmd=pigean_cmd,
            cwd=pigean_repo,
            env=env,
            stdout_path=pigean_stdout,
            stderr_path=pigean_stderr,
        )
        pigean_status = classify_no_enrichment(pigean_returncode, pigean_stdout_text, pigean_stderr_text, pigean_bundle)

        eaggl_factors = set_output_dir / "eaggl.factors.v1.tsv"
        eaggl_gene_set_clusters = set_output_dir / "eaggl.gene_set_clusters.v1.tsv"
        eaggl_gene_clusters = set_output_dir / "eaggl.gene_clusters.v1.tsv"
        eaggl_params = set_output_dir / "eaggl.params.v1.tsv"
        eaggl_stdout = set_output_dir / "eaggl.stdout.v1.log"
        eaggl_stderr = set_output_dir / "eaggl.stderr.v1.log"
        eaggl_returncode = ""
        eaggl_status = "skipped"
        if pigean_status == "success":
            eaggl_cmd = [
                python_executable,
                "-m",
                "eaggl",
                "factor",
                "--eaggl-bundle-in",
                str(pigean_bundle),
                "--gene-set-stats-id-col",
                "Gene_Set",
                "--gene-set-stats-beta-tilde-col",
                "beta_tilde",
                "--gene-stats-id-col",
                "Gene",
                "--gene-stats-log-bf-col",
                "log_bf",
                "--factors-out",
                str(eaggl_factors),
                "--gene-set-clusters-out",
                str(eaggl_gene_set_clusters),
                "--gene-clusters-out",
                str(eaggl_gene_clusters),
                "--params-out",
                str(eaggl_params),
            ]
            append_command(command_rows, step="eaggl_factor", workdir=pigean_repo, cmd=eaggl_cmd, metadata={"canonical_set_name": canonical_set_name})
            eaggl_returncode, eaggl_stdout_text, eaggl_stderr_text = run_command_logged(
                step_name="eaggl_factor",
                cmd=eaggl_cmd,
                cwd=pigean_repo,
                env=env,
                stdout_path=eaggl_stdout,
                stderr_path=eaggl_stderr,
            )
            eaggl_status = classify_no_enrichment(int(eaggl_returncode), eaggl_stdout_text, eaggl_stderr_text, eaggl_factors)

        pigean_keyword_hits: list[str] = []
        eaggl_keyword_hits: list[str] = []
        if pigean_gene_set_stats.exists():
            pigean_df = pd.read_csv(pigean_gene_set_stats, sep="\t", dtype=str)
            top_pigean_terms = pigean_df["Gene_Set"].head(20).fillna("").tolist() if "Gene_Set" in pigean_df.columns else []
            pigean_keyword_hits = keyword_hits(top_pigean_terms)
        if eaggl_factors.exists():
            eaggl_df = pd.read_csv(eaggl_factors, sep="\t", dtype=str)
            text_values: list[str] = []
            for column in ["label", "top_gene_sets", "top_genes"]:
                if column in eaggl_df.columns:
                    text_values.extend(eaggl_df[column].head(10).fillna("").tolist())
            eaggl_keyword_hits = keyword_hits(text_values)
        combined_hits = sorted(set(pigean_keyword_hits + eaggl_keyword_hits))

        rows.append(
            {
                "canonical_set_name": canonical_set_name,
                "base_set_name": str(row["base_set_name"]),
                "representative_model_name": str(row["representative_model_name"]),
                "collapsed_model_names": str(row["collapsed_model_names"]),
                "n_input_genes": len(genes),
                "pigean_status": pigean_status,
                "eaggl_status": eaggl_status,
                "pigean_gene_set_stats_out": str(pigean_gene_set_stats) if pigean_gene_set_stats.exists() else "",
                "eaggl_factors_out": str(eaggl_factors) if eaggl_factors.exists() else "",
                "pigean_keyword_hits": ",".join(pigean_keyword_hits),
                "eaggl_keyword_hits": ",".join(eaggl_keyword_hits),
                "combined_keyword_hits": ",".join(combined_hits),
                "n_combined_keyword_hits": len(combined_hits),
                "captures_relevant_biology": len(combined_hits) > 0,
            }
        )

    summary_df = pd.DataFrame(rows).sort_values(["captures_relevant_biology", "n_combined_keyword_hits", "canonical_set_name"], ascending=[False, False, True]).reset_index(drop=True)
    return summary_df


def build_model_relevance_summary(canonical_analysis_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    by_model: dict[str, dict[str, object]] = {}
    for _, row in canonical_analysis_df.iterrows():
        collapsed_models = [part for part in str(row["collapsed_model_names"]).split(",") if part]
        for model_name in collapsed_models:
            entry = by_model.setdefault(
                model_name,
                {
                    "model_name": model_name,
                    "n_canonical_sets": 0,
                    "n_relevant_canonical_sets": 0,
                    "max_keyword_hit_count": 0,
                    "relevant_canonical_set_names": [],
                    "keyword_hits": set(),
                },
            )
            entry["n_canonical_sets"] += 1
            hit_count = int(row["n_combined_keyword_hits"])
            entry["max_keyword_hit_count"] = max(entry["max_keyword_hit_count"], hit_count)
            if bool(row["captures_relevant_biology"]):
                entry["n_relevant_canonical_sets"] += 1
                entry["relevant_canonical_set_names"].append(str(row["canonical_set_name"]))
                for hit in [part for part in str(row["combined_keyword_hits"]).split(",") if part]:
                    entry["keyword_hits"].add(hit)
    for entry in by_model.values():
        rows.append(
            {
                "model_name": entry["model_name"],
                "n_canonical_sets": entry["n_canonical_sets"],
                "n_relevant_canonical_sets": entry["n_relevant_canonical_sets"],
                "max_keyword_hit_count": entry["max_keyword_hit_count"],
                "captures_relevant_biology": entry["n_relevant_canonical_sets"] > 0,
                "keyword_hits": ",".join(sorted(entry["keyword_hits"])),
                "relevant_canonical_set_names": ",".join(entry["relevant_canonical_set_names"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["captures_relevant_biology", "n_relevant_canonical_sets", "max_keyword_hit_count", "model_name"], ascending=[False, False, False, True]).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_gtex_model_sweep_adipose.v1.log")
    repo_root = resolve_repo_root(output_dir)
    workflow_repo = Path(args.workflow_repo).resolve()
    pigean_repo = Path(args.pigean_repo).resolve()
    reference_gmt_gz = Path(args.reference_gmt_gz).resolve()

    base_model_run_plan_df = pd.read_csv(Path(args.base_model_run_plan_tsv).resolve(), sep="\t", dtype=str)
    base_workflow_run_plan_df = pd.read_csv(Path(args.base_workflow_run_plan_tsv).resolve(), sep="\t", dtype=str)
    LOGGER.info(
        "loaded plans model_shape=%s workflow_shape=%s",
        base_model_run_plan_df.shape,
        base_workflow_run_plan_df.shape,
    )

    harmonizome_module = load_module("gtex_harmonizome_analysis_v1", repo_root / "src" / "run_gtex_harmonizome_analysis.v1.py")
    tissue_row = build_tissue_row(repo_root)
    reference_adipose_gmt_gz = write_reference_subset(reference_gmt_gz, output_dir)
    command_rows: list[dict[str, object]] = []

    workflow_output_rows: list[dict[str, object]] = []
    for _, workflow_row in base_workflow_run_plan_df.iterrows():
        workflow_output_rows.append(
            run_adipose_workflow(
                workflow_row=workflow_row,
                tissue_row=tissue_row,
                workflow_repo=workflow_repo,
                python_executable=args.python_executable,
                output_dir=output_dir,
                repo_root=repo_root,
                resume=args.resume,
                command_rows=command_rows,
            )
        )
    workflow_outputs_df = pd.DataFrame(workflow_output_rows).sort_values("workflow_name").reset_index(drop=True)
    workflow_output_by_name = {str(row["workflow_name"]): row.to_dict() for _, row in workflow_outputs_df.iterrows()}
    workflow_summary_path = output_dir / "workflow_summary.v1.tsv"
    write_dataframe(workflow_outputs_df, workflow_summary_path)
    write_markdown_for_table(
        workflow_summary_path,
        "Adipose Workflow Summary v1",
        bullets=[
            f"tissue: `{ADIPOSE_TISSUE}`",
            f"workflow_count: {int(workflow_outputs_df.shape[0])}",
            f"reused_existing: {int((workflow_outputs_df['status'] == 'reused_existing').sum())}",
            f"newly_run: {int((workflow_outputs_df['status'] == 'completed').sum())}",
        ],
    )

    model_output_rows: list[dict[str, object]] = []
    for _, model_row in base_model_run_plan_df.iterrows():
        model_output_rows.append(
            run_model(
                model_row=model_row,
                workflow_output_by_name=workflow_output_by_name,
                workflow_repo=workflow_repo,
                python_executable=args.python_executable,
                output_dir=output_dir,
                reference_adipose_gmt_gz=reference_adipose_gmt_gz,
                harmonizome_module=harmonizome_module,
                resume=args.resume,
                command_rows=command_rows,
            )
        )
    model_outputs_df = pd.DataFrame(model_output_rows).sort_values("model_name").reset_index(drop=True)
    model_summary_path = output_dir / "model_summary.v1.tsv"
    write_dataframe(model_outputs_df, model_summary_path)
    write_markdown_for_table(
        model_summary_path,
        "Adipose Model Summary v1",
        bullets=[
            f"tissue: `{ADIPOSE_TISSUE}`",
            f"model_count: {int(model_outputs_df.shape[0])}",
            f"min_adipose_set_count: {int(model_outputs_df['n_adipose_sets'].min())}",
            f"max_adipose_set_count: {int(model_outputs_df['n_adipose_sets'].max())}",
        ],
    )

    canonical_df, model_redundancy_df, canonical_gmt_gz = build_canonical_outputs(model_outputs_df, output_dir)
    canonical_summary_path = output_dir / "canonical_gene_sets.v1.tsv"
    write_dataframe(canonical_df, canonical_summary_path)
    write_markdown_for_table(
        canonical_summary_path,
        "Canonical Adipose Gene Sets v1",
        bullets=[
            f"canonical_gmt_gz: `{canonical_gmt_gz.name}`",
            f"canonical_set_count: {int(canonical_df.shape[0])}",
            f"collapsed_duplicate_sets: {int((canonical_df['n_models_collapsed'] > 1).sum())}",
            "deduplication_key: exact `base_set_name` plus exact ordered gene membership",
        ],
        notes=[
            "The canonical GMT retains one representative row for each exact redundant gene list.",
            "Representative names append the representative model name to the original GTEx set name with an underscore delimiter.",
        ],
    )
    model_redundancy_path = output_dir / "model_redundancy_summary.v1.tsv"
    write_dataframe(model_redundancy_df, model_redundancy_path)
    write_markdown_for_table(
        model_redundancy_path,
        "Model Redundancy Summary v1",
        bullets=[
            f"model_count: {int(model_redundancy_df.shape[0])}",
            f"models_with_collapsed_sets: {int((model_redundancy_df['n_sets_collapsed_away'] > 0).sum())}",
        ],
    )

    canonical_analysis_df = run_pigean_eaggl_on_canonical_sets(
        canonical_df=canonical_df,
        canonical_gmt_gz=canonical_gmt_gz,
        output_dir=output_dir,
        pigean_repo=pigean_repo,
        python_executable=args.python_executable,
        command_rows=command_rows,
    )
    canonical_analysis_path = output_dir / "canonical_pigean_eaggl_summary.v1.tsv"
    write_dataframe(canonical_analysis_df, canonical_analysis_path)
    write_markdown_for_table(
        canonical_analysis_path,
        "Canonical PIGEAN EAGGL Summary v1",
        bullets=[
            f"canonical_set_count: {int(canonical_analysis_df.shape[0])}",
            f"pigean_success: {int((canonical_analysis_df['pigean_status'] == 'success').sum())}",
            f"eaggl_success: {int((canonical_analysis_df['eaggl_status'] == 'success').sum())}",
            f"canonical_sets_with_adipose_keyword_hits: {int(canonical_analysis_df['captures_relevant_biology'].sum())}",
        ],
        notes=[
            "Relevant-biology calls are heuristic and based on adipose-related keyword hits in top PIGEAN enriched gene-set names and top EAGGL factor labels/gene-set labels.",
            "Keywords include adipose, adipocyte, lipid, fatty, PPAR, insulin, glucose, leptin, thermogenesis, visceral, subcutaneous, and related stems.",
        ],
    )

    model_relevance_df = build_model_relevance_summary(canonical_analysis_df)
    relevant_models_path = output_dir / "relevant_models.v1.tsv"
    write_dataframe(model_relevance_df, relevant_models_path)
    write_markdown_for_table(
        relevant_models_path,
        "Relevant Models v1",
        bullets=[
            f"model_count: {int(model_relevance_df.shape[0])}",
            f"models_flagged_relevant: {int(model_relevance_df['captures_relevant_biology'].sum())}",
            "ranking: flagged models sorted by number of relevant canonical sets, then maximum keyword-hit count",
        ],
        notes=[
            "This is a preliminary filter, not a final biological validation.",
            "Models can inherit relevance credit from canonical sets that were exact duplicates across multiple models.",
        ],
    )

    commands_df = pd.DataFrame(command_rows)
    commands_path = output_dir / "commands_executed.v1.tsv"
    write_dataframe(commands_df, commands_path)
    write_markdown_for_table(
        commands_path,
        "Commands Executed v1",
        bullets=[
            f"command_count: {int(commands_df.shape[0])}",
            "includes: workflow DE commands, model conversion commands, PIGEAN commands, and EAGGL commands",
        ],
    )

    run_summary_df = pd.DataFrame(
        [
            {"metric": "analysis_name", "value": "gtex_model_sweep_adipose_v1"},
            {"metric": "tissue", "value": ADIPOSE_TISSUE},
            {"metric": "workflow_count", "value": int(workflow_outputs_df.shape[0])},
            {"metric": "model_count", "value": int(model_outputs_df.shape[0])},
            {"metric": "canonical_set_count", "value": int(canonical_df.shape[0])},
            {"metric": "relevant_model_count", "value": int(model_relevance_df["captures_relevant_biology"].sum())},
            {"metric": "pigean_success_count", "value": int((canonical_analysis_df["pigean_status"] == "success").sum())},
            {"metric": "eaggl_success_count", "value": int((canonical_analysis_df["eaggl_status"] == "success").sum())},
        ]
    )
    run_summary_path = output_dir / "run_summary.v1.tsv"
    write_dataframe(run_summary_df, run_summary_path)
    write_markdown_for_table(
        run_summary_path,
        "GTEx Model Sweep Adipose Summary v1",
        bullets=[
            f"analysis_name: `gtex_model_sweep_adipose_v1`",
            f"tissue: `{ADIPOSE_TISSUE}`",
            f"workflow_count: {int(workflow_outputs_df.shape[0])}",
            f"model_count: {int(model_outputs_df.shape[0])}",
            f"canonical_set_count: {int(canonical_df.shape[0])}",
            f"relevant_model_count: {int(model_relevance_df['captures_relevant_biology'].sum())}",
        ],
    )


if __name__ == "__main__":
    main()
