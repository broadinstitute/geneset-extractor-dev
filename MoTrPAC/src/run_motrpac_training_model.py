#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from motrpac_selection_io import default_model_manifest_path


CANONICAL_TISSUE_TERMS: dict[str, str] = {
    "adrenals": "T60-Adrenals",
    "blood": "T30-Blood-RNA",
    "brown_adipose": "T69-Brown-Adipose",
    "colon": "T61-Colon",
    "cortex": "T53-Cortex",
    "gastrocnemius": "T55-Gastrocnemius",
    "heart": "T58-Heart",
    "hippocampus": "T52-Hippocampus",
    "hypothalamus": "T54-Hypothalamus",
    "kidney": "T59-Kidney",
    "liver": "T68-Liver",
    "lung": "T66-Lung",
    "ovaries": "T64-Ovaries",
    "small_intestine": "T67-Small-Intestine",
    "spleen": "T62-Spleen",
    "testes": "T63-Testes",
    "vastus_lateralis": "T56-Vastus-Lateralis",
    "vena_cava": "T99-Vena-Cava",
    "white_adipose": "T70-White-Adipose",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one MoTrPAC training model and emit human-mapped gene-set outputs."
    )
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--prepared_dir")
    parser.add_argument("--counts_tsv")
    parser.add_argument("--tissue_label")
    parser.add_argument("--transcript_tissue_label")
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--raw_counts_tsv")
    parser.add_argument("--transcript_metadata_tsv")
    parser.add_argument("--phenotype_metadata_tsv")
    parser.add_argument("--feature_to_gene_tsv")
    parser.add_argument("--rat_to_human_tsv")
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", default="Rscript")
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--model_manifest", default=str(default_model_manifest_path()))
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def load_model_settings(manifest_path: Path) -> dict[str, dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    settings: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if model_id:
            settings[model_id] = {str(key): str(value) for key, value in row.items()}
    if not settings:
        raise SystemExit(f"No model settings found in {manifest_path}")
    return settings


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def resolve_rscript_bin(rscript_bin: str) -> str:
    resolved = shutil.which(rscript_bin) if not Path(rscript_bin).is_absolute() else rscript_bin
    if not resolved or not Path(resolved).exists():
        raise SystemExit(f"Rscript not found: {rscript_bin}")
    return resolved


def check_r_packages(rscript_bin: str) -> None:
    cmd = [
        rscript_bin,
        "--vanilla",
        "-e",
        "quit(status=if (requireNamespace('edgeR', quietly=TRUE) && requireNamespace('limma', quietly=TRUE)) 0 else 1)",
    ]
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(
            "R packages 'edgeR' and 'limma' are required for the MoTrPAC training workflow and were not found for "
            f"{rscript_bin}."
        )


def motrpac_training_signature_name(*, tissue_id: str, tissue_label: str | None) -> str:
    tissue_term = CANONICAL_TISSUE_TERMS.get(str(tissue_id).strip(), "")
    if not tissue_term:
        fallback = str(tissue_label or tissue_id).strip()
        tissue_term = fallback.replace(" ", "-")
    return f"MoTrPAC_{tissue_term}_TrainingVsControl"


def write_workflow_script(
    *,
    script_path: Path,
    counts_tsv: Path,
    metadata_tsv: Path,
    output_tsv: Path,
    include_sex: bool,
) -> None:
    formula_expr = "~ intervention + sex" if include_sex else "~ intervention"
    coef_name = "interventiontraining"
    model_formula_label = "intervention + sex" if include_sex else "intervention"
    script = f'''suppressPackageStartupMessages({{
  library(edgeR)
  library(limma)
}})

counts <- read.delim("{counts_tsv}", check.names=FALSE)
meta <- read.delim("{metadata_tsv}", check.names=FALSE)
count_cols <- setdiff(colnames(counts), c("gene_id", "gene_symbol"))
count_mat <- as.matrix(counts[, count_cols, drop=FALSE])
storage.mode(count_mat) <- "numeric"
rownames(count_mat) <- counts$gene_id
gene_ids <- counts$gene_id
gene_symbols <- as.character(counts$gene_symbol)

meta$sample_id <- as.character(meta$sample_id)
meta$sex <- factor(as.character(meta$sex), levels=c("M", "F"))
meta$intervention <- factor(as.character(meta$intervention), levels=c("control", "training"))
count_mat <- count_mat[, meta$sample_id, drop=FALSE]
y <- DGEList(counts=count_mat)
design <- model.matrix({formula_expr}, data=meta)
keep_genes <- filterByExpr(y, design=design)
y <- y[keep_genes, , keep.lib.sizes=FALSE]
gene_ids <- gene_ids[keep_genes]
gene_symbols <- gene_symbols[keep_genes]
y <- calcNormFactors(y)
v <- voom(y, design, plot=FALSE)
fit <- lmFit(v, design)
fit <- eBayes(fit)
tt <- topTable(fit, coef="{coef_name}", number=Inf, sort.by="none")
tt$comparison_id <- "training_vs_control"
tt$gene_id <- gene_ids
tt$gene_symbol <- gene_symbols
tt$group_a <- "training"
tt$group_b <- "control"
tt$stratum <- ""
tt$backend <- "r_limma_voom_motrpac_training"
tt$n_group_a <- sum(meta$intervention == "training")
tt$n_group_b <- sum(meta$intervention == "control")
tt$mean_expr <- tt$AveExpr
tt$model_formula <- "{model_formula_label}"
keep_cols <- c("comparison_id", "gene_id", "gene_symbol", "logFC", "t", "P.Value", "adj.P.Val", "group_a", "group_b", "stratum", "backend", "n_group_a", "n_group_b", "mean_expr", "model_formula")
tt <- tt[, keep_cols, drop=FALSE]
colnames(tt)[colnames(tt) == "t"] <- "stat"
colnames(tt)[colnames(tt) == "P.Value"] <- "pvalue"
colnames(tt)[colnames(tt) == "adj.P.Val"] <- "padj"
write.table(tt, file="{output_tsv}", sep="\\t", row.names=FALSE, quote=FALSE)
'''
    write_text(script_path, script)


def build_extractor_cmd(
    *,
    python_bin: str,
    deg_tsv: Path,
    extractor_out: Path,
    organism: str,
    genome_build: str,
    signature_name: str,
    settings: dict[str, str],
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg",
        "--deg_tsv",
        str(deg_tsv),
        "--out_dir",
        str(extractor_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--signature_name",
        signature_name,
        "--postprocess_mode",
        settings["extractor_postprocess_mode"],
        "--score_mode",
        settings["extractor_score_mode"],
        "--select",
        settings["extractor_select"],
        "--normalize",
        "within_set_l1",
        "--emit_full",
        "true",
        "--emit_gmt",
        "true",
        "--gmt_split_signed",
        "true",
        "--gmt_name_separator",
        "_",
        "--gmt_signed_labels",
        "up_dn",
        "--gmt_require_symbol",
        settings["extractor_gmt_require_symbol"],
        "--emit_small_gene_sets",
        settings["extractor_emit_small_gene_sets"],
    ]
    if settings["extractor_disable_default_excludes"] == "true":
        cmd.append("--disable_default_excludes")
    for flag_name, key in [
        ("--padj_max", "extractor_padj_max"),
        ("--pvalue_max", "extractor_pvalue_max"),
        ("--min_abs_logfc", "extractor_min_abs_logfc"),
        ("--top_k", "extractor_top_k"),
        ("--min_score", "extractor_min_score"),
        ("--gmt_source", "extractor_gmt_source"),
        ("--gmt_topk_list", "extractor_gmt_topk_list"),
        ("--gmt_min_genes", "extractor_gmt_min_genes"),
        ("--gmt_max_genes", "extractor_gmt_max_genes"),
    ]:
        value = settings[key]
        if value != "NA":
            cmd.extend([flag_name, value])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def build_workflow_cmd(
    *,
    python_bin: str,
    prepared_dir: Path | None,
    workflow_out: Path,
    organism: str,
    genome_build: str,
    rscript_bin: str,
    include_sex: bool,
    counts_tsv: str | None,
    tissue_label: str | None,
    transcript_tissue_label: str | None,
    raw_counts_tsv: str | None,
    transcript_metadata_tsv: str | None,
    phenotype_metadata_tsv: str | None,
    feature_to_gene_tsv: str | None,
    rat_to_human_tsv: str | None,
    provenance_mirror_local_prefix: str | None,
    provenance_mirror_remote_prefix: str | None,
) -> list[str]:
    counts_arg = counts_tsv or raw_counts_tsv
    if not counts_arg:
        raise SystemExit("MoTrPAC training runner requires --counts_tsv or --raw_counts_tsv.")
    cmd = [
        python_bin,
        "-m",
        "geneset_extractors.cli",
        "workflows",
        "motrpac_training",
        "--counts_tsv",
        counts_arg,
        "--out_dir",
        str(workflow_out),
        "--organism",
        organism,
        "--genome_build",
        genome_build,
        "--rscript_bin",
        rscript_bin,
        "--covariates",
        "sex" if include_sex else "none",
    ]
    if prepared_dir is not None:
        cmd.extend(["--sample_metadata_tsv", str(prepared_dir / "sample_metadata.tsv")])
    else:
        if not tissue_label or not transcript_tissue_label:
            raise SystemExit("MoTrPAC training runner requires --tissue_label and --transcript_tissue_label when --prepared_dir is omitted.")
        cmd.extend(
            [
                "--tissue_label",
                tissue_label,
                "--transcript_tissue_label",
                transcript_tissue_label,
            ]
        )
    if raw_counts_tsv:
        cmd.extend(["--raw_counts_tsv", raw_counts_tsv])
    if transcript_metadata_tsv:
        cmd.extend(["--transcript_metadata_tsv", transcript_metadata_tsv])
    if phenotype_metadata_tsv:
        cmd.extend(["--phenotype_metadata_tsv", phenotype_metadata_tsv])
    if feature_to_gene_tsv:
        cmd.extend(["--feature_to_gene_tsv", feature_to_gene_tsv])
    if rat_to_human_tsv:
        cmd.extend(["--rat_to_human_tsv", rat_to_human_tsv])
    if provenance_mirror_local_prefix:
        cmd.extend(["--provenance_mirror_local_prefix", provenance_mirror_local_prefix])
    if provenance_mirror_remote_prefix:
        cmd.extend(["--provenance_mirror_remote_prefix", provenance_mirror_remote_prefix])
    return cmd


def run_command(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> None:
    log_line(log_path, f"$ {shell_join(cmd)}")
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.stdout:
        log_line(log_path, completed.stdout.rstrip("\n"))
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)


def write_model_commands(
    *,
    model_out: Path,
    model_id: str,
    workflow_cmd: list[str],
    extractor_cmd: list[str],
    dig_dir: Path,
) -> None:
    text = "\n".join(
        [
            f"# Commands For {model_id}",
            "",
            "## Workflow",
            "",
            "```bash",
            shell_join(workflow_cmd),
            "```",
            "",
            "## Extractor",
            "",
            "```bash",
            f"cd {shlex.quote(str(dig_dir))}",
            f"PYTHONPATH={shlex.quote(str(dig_dir / 'src'))} {shell_join(extractor_cmd)}",
            "```",
            "",
        ]
    )
    write_text(model_out / "commands.md", text)


def main() -> int:
    args = parse_args()
    settings_by_model = load_model_settings(Path(args.model_manifest))
    if args.model_id not in settings_by_model:
        raise SystemExit(f"Unsupported model_id: {args.model_id}")
    settings = settings_by_model[args.model_id]

    prepared_dir = Path(args.prepared_dir).resolve() if args.prepared_dir else None
    run_root = Path(args.run_root).resolve()
    model_out = run_root / args.model_id
    workflow_out = model_out / "workflow"
    extractor_out = model_out / "extractor"
    dig_dir = Path(args.dig_dir).resolve()
    if not dig_dir.exists():
        raise SystemExit(f"Missing dig-gene-set-extractors directory: {dig_dir}")

    model_out.mkdir(parents=True, exist_ok=True)
    workflow_out.mkdir(parents=True, exist_ok=True)
    extractor_out.mkdir(parents=True, exist_ok=True)

    include_sex = str(settings.get("workflow_covariates", "sex")).strip().lower() != "none"
    deg_tsv = workflow_out / "training_deg.tsv"
    workflow_cmd = build_workflow_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        prepared_dir=prepared_dir,
        workflow_out=workflow_out,
        organism=args.organism,
        genome_build=args.genome_build,
        rscript_bin=args.rscript_bin,
        include_sex=include_sex,
        counts_tsv=args.counts_tsv,
        tissue_label=args.tissue_label,
        transcript_tissue_label=args.transcript_tissue_label,
        raw_counts_tsv=args.raw_counts_tsv,
        transcript_metadata_tsv=args.transcript_metadata_tsv,
        phenotype_metadata_tsv=args.phenotype_metadata_tsv,
        feature_to_gene_tsv=args.feature_to_gene_tsv,
        rat_to_human_tsv=args.rat_to_human_tsv,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    extractor_cmd = build_extractor_cmd(
        python_bin=str(Path(args.python_bin).resolve()),
        deg_tsv=deg_tsv,
        extractor_out=extractor_out,
        organism=args.organism,
        genome_build=args.genome_build,
        signature_name=motrpac_training_signature_name(
            tissue_id=args.tissue_id,
            tissue_label=args.tissue_label,
        ),
        settings=settings,
        provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
        provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
    )
    write_model_commands(
        model_out=model_out,
        model_id=args.model_id,
        workflow_cmd=workflow_cmd,
        extractor_cmd=extractor_cmd,
        dig_dir=dig_dir,
    )
    if args.write_commands_only:
        return 0

    env = dict(os.environ)
    env["PYTHONPATH"] = str(dig_dir / "src")
    model_log = model_out / "run.log"
    run_command(workflow_cmd, cwd=dig_dir, env=env, log_path=model_log)
    run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
