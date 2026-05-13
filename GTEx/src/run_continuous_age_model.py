from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from selection_io import default_continuous_age_model_manifest_path

AGE_BIN_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run GTEx tissue-level continuous-age workflows and emit one tissue-level "
            "GMT per model from a single regression across all retained tissue samples."
        )
    )
    parser.add_argument("--tissue_id", required=True)
    parser.add_argument("--model_ids", default="all", help="comma-separated model IDs or 'all'")
    parser.add_argument("--prepared_dir", required=True)
    parser.add_argument("--run_root", required=True)
    parser.add_argument("--python_bin", default=sys.executable or "python3")
    parser.add_argument("--rscript_bin", required=True)
    parser.add_argument("--organism", default="human", choices=["human", "mouse"])
    parser.add_argument("--genome_build", default="hg38")
    parser.add_argument("--gtf")
    parser.add_argument("--provenance_mirror_local_prefix")
    parser.add_argument("--provenance_mirror_remote_prefix")
    parser.add_argument("--dig_dir", required=True)
    parser.add_argument("--continuous_age_model_manifest", default=str(default_continuous_age_model_manifest_path()))
    parser.add_argument("--write_commands_only", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_input_path(path_value: str | None, *, base_dir: Path) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def _model_sort_key(model_id: str) -> tuple[str, int]:
    prefix = "".join(ch for ch in model_id if not ch.isdigit())
    suffix = "".join(ch for ch in model_id if ch.isdigit())
    return prefix, int(suffix or "0")


def load_tissue_model_settings(manifest_path: Path) -> dict[str, dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise SystemExit(f"No rows found in tissue model manifest: {manifest_path}")
    settings: dict[str, dict[str, str]] = {}
    for row in rows:
        model_id = str(row.get("model_id", "")).strip()
        if not model_id:
            continue
        settings[model_id] = {str(key): str(value) for key, value in row.items()}
    if not settings:
        raise SystemExit(f"No model IDs found in tissue model manifest: {manifest_path}")
    return settings


def parse_model_ids(text: str, model_settings: dict[str, dict[str, str]]) -> list[str]:
    if text.strip().lower() == "all":
        return sorted(model_settings, key=_model_sort_key)
    model_ids = [item.strip() for item in text.split(",") if item.strip()]
    unknown = [model_id for model_id in model_ids if model_id not in model_settings]
    if unknown:
        raise SystemExit(f"Unsupported model IDs: {', '.join(unknown)}")
    return model_ids


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text.rstrip("\n") + "\n")


def parse_age_midpoint(age_bin: str) -> float:
    match = AGE_BIN_PATTERN.match(age_bin)
    if not match:
        raise ValueError(f"Unsupported age_bin format: {age_bin}")
    lower = float(match.group(1))
    upper = float(match.group(2))
    return (lower + upper) / 2.0


def prepare_continuous_metadata(prepared_dir: Path, out_tsv: Path) -> dict[str, Any]:
    with (prepared_dir / "sample_metadata.tsv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)

    out_rows: list[dict[str, str]] = []
    age_values: list[float] = []
    for row in rows:
        age_mid = parse_age_midpoint(str(row.get("age_bin", "")).strip())
        age_values.append(age_mid)
        out_rows.append(
            {
                **{str(k): str(v) for k, v in row.items()},
                "age_mid": f"{age_mid:.1f}",
            }
        )

    write_tsv(
        out_tsv,
        out_rows,
        ["sample_id", "subject_id", "age_bin", "age_mid", "SEX", "primary_tissue", "detailed_tissue"],
    )
    write_text(
        out_tsv.with_suffix(".md"),
        "\n".join(
            [
                "# Continuous-Age Metadata",
                "",
                "This metadata adds `age_mid`, the midpoint of the GTEx age bin used as a continuous predictor.",
                "",
                "- `20-29` -> `24.5`",
                "- `30-39` -> `34.5`",
                "- `40-49` -> `44.5`",
                "- `50-59` -> `54.5`",
                "- `60-69` -> `64.5`",
                "- `70-79` -> `74.5`",
                "",
            ]
        ),
    )
    write_text(out_tsv.with_suffix(".log"), f"wrote {len(out_rows)} rows\n")
    return {
        "n_samples": len(out_rows),
        "age_mid_min": min(age_values) if age_values else None,
        "age_mid_max": max(age_values) if age_values else None,
    }


def write_continuous_age_r_script(
    *,
    script_path: Path,
    counts_tsv: Path,
    metadata_tsv: Path,
    output_tsv: Path,
    include_sex: bool,
) -> Path:
    formula_terms = ["age_mid"]
    if include_sex:
        formula_terms.append("SEX")
    formula_expr = " + ".join(formula_terms)
    script = f'''suppressPackageStartupMessages({{
  library(edgeR)
  library(limma)
}})

counts <- read.delim("{counts_tsv}", check.names=FALSE)
meta <- read.delim("{metadata_tsv}", check.names=FALSE)
feature_ids <- counts[[1]]
gene_symbols <- if ("gene_symbol" %in% colnames(counts)) as.character(counts[["gene_symbol"]]) else as.character(feature_ids)
count_cols <- setdiff(colnames(counts), c(colnames(counts)[1], "gene_symbol"))
count_mat <- as.matrix(counts[, count_cols, drop=FALSE])
storage.mode(count_mat) <- "numeric"
rownames(count_mat) <- feature_ids
meta$sample_id <- as.character(meta$sample_id)
meta$SEX <- factor(as.character(meta$SEX))
meta$age_mid <- as.numeric(meta$age_mid)
count_mat <- count_mat[, meta$sample_id, drop=FALSE]
y <- DGEList(counts=count_mat)
keep_genes <- filterByExpr(y)
y <- y[keep_genes, , keep.lib.sizes=FALSE]
y <- calcNormFactors(y)
design <- model.matrix(as.formula("~ {formula_expr}"), data=meta)
v <- voom(y, design, plot=FALSE)
fit <- lmFit(v, design)
coef_name <- "age_mid"
fit <- eBayes(fit)
tt <- topTable(fit, coef=coef_name, number=Inf, sort.by="none")
tt$comparison_id <- "continuous_age"
tt$gene_id <- rownames(tt)
tt$gene_symbol <- gene_symbols[match(rownames(tt), feature_ids)]
tt$group_a <- "older"
tt$group_b <- "younger"
tt$stratum <- ""
tt$backend <- "r_limma_voom_continuous_age"
tt$n_group_a <- nrow(meta)
tt$n_group_b <- nrow(meta)
tt$mean_expr <- tt$AveExpr
tt$model_formula <- "{formula_expr}"
keep_cols <- c("comparison_id", "gene_id", "gene_symbol", "logFC", "t", "P.Value", "adj.P.Val", "group_a", "group_b", "stratum", "backend", "n_group_a", "n_group_b", "mean_expr", "model_formula")
tt <- tt[, keep_cols, drop=FALSE]
colnames(tt)[colnames(tt) == "t"] <- "stat"
colnames(tt)[colnames(tt) == "P.Value"] <- "pvalue"
colnames(tt)[colnames(tt) == "adj.P.Val"] <- "padj"
write.table(tt, file="{output_tsv}", sep="\\t", row.names=FALSE, quote=FALSE)
'''
    write_text(script_path, script)
    return script_path


def build_workflow_cmd(
    *,
    rscript_bin: str,
    workflow_script: Path,
) -> list[str]:
    return [rscript_bin, str(workflow_script)]


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
            "R packages 'edgeR' and 'limma' are required for the continuous-age tissue workflow and were not found for "
            f"{rscript_bin}."
        )


def build_extractor_cmd(
    *,
    python_bin: str,
    deg_tsv: Path,
    extractor_out: Path,
    organism: str,
    genome_build: str,
    settings: dict[str, str],
    signature_name: str,
    gtf_path: str | None,
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
        settings["EXTRACTOR_POSTPROCESS_MODE"],
        "--score_mode",
        settings["EXTRACTOR_SCORE_MODE"],
        "--select",
        settings["EXTRACTOR_SELECT"],
        "--normalize",
        "within_set_l1",
        "--emit_full",
        "true",
        "--emit_gmt",
        "true",
        "--gmt_split_signed",
        "true",
        "--gmt_require_symbol",
        settings["EXTRACTOR_GMT_REQUIRE_SYMBOL"],
        "--emit_small_gene_sets",
        settings["EXTRACTOR_EMIT_SMALL_GENE_SETS"],
    ]
    if settings["EXTRACTOR_DISABLE_DEFAULT_EXCLUDES"] == "true":
        cmd.append("--disable_default_excludes")
    for flag_name, key in [
        ("--padj_max", "EXTRACTOR_PADJ_MAX"),
        ("--pvalue_max", "EXTRACTOR_PVALUE_MAX"),
        ("--min_abs_logfc", "EXTRACTOR_MIN_ABS_LOGFC"),
        ("--top_k", "EXTRACTOR_TOP_K"),
        ("--min_score", "EXTRACTOR_MIN_SCORE"),
        ("--gmt_source", "EXTRACTOR_GMT_SOURCE"),
        ("--gmt_topk_list", "EXTRACTOR_GMT_TOPK_LIST"),
        ("--gmt_min_genes", "EXTRACTOR_GMT_MIN_GENES"),
        ("--gmt_max_genes", "EXTRACTOR_GMT_MAX_GENES"),
    ]:
        value = settings[key]
        if value != "NA":
            cmd.extend([flag_name, value])
    if settings["EXTRACTOR_GMT_BIOTYPE_ALLOWLIST"]:
        cmd.extend(["--gmt_biotype_allowlist", settings["EXTRACTOR_GMT_BIOTYPE_ALLOWLIST"]])
    if settings["ANNOTATION_MODE"] == "gtf_annotated":
        if not gtf_path:
            raise SystemExit("Models AC3 and AC4 require --gtf")
        cmd.extend(["--gtf", gtf_path])
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
    tissue_deg_tsv: Path,
    repo: Path,
    dig_dir: Path,
) -> None:
    text = "\n".join(
        [
            f"# Commands For {model_id}",
            "",
            "## Continuous-Age Workflow",
            "",
            "```bash",
            shell_join(workflow_cmd),
            "```",
            "",
            "## Tissue DEG Model",
            "",
            "The runner fits one limma/voom model across all tissue samples with continuous `age_mid` as the predictor of interest.",
            "",
            "The DEG table is written at:",
            f"- `{tissue_deg_tsv}`",
            "",
            "Interpretation:",
            "- positive `logFC` / `stat`: expression increases with age",
            "- negative `logFC` / `stat`: expression decreases with age",
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


def write_tissue_method_note(path: Path, tissue_id: str, model_id: str) -> None:
    text = f"""# Tissue-Level GMT Naming

This extractor emits one combined GMT for `{tissue_id}` under model `{model_id}`.

Examples:
- `{model_id}__{tissue_id}__pos`: genes with positive age-associated scores
- `{model_id}__{tissue_id}__neg`: genes with negative age-associated scores

These are derived from one continuous-age regression across all retained tissue samples, not from separate age-bin contrasts.
"""
    write_text(path, text)


def write_tissue_deg_note(path: Path, tissue_id: str, model_id: str, include_sex: bool) -> None:
    formula = "age_mid + SEX" if include_sex else "age_mid"
    text = f"""# Tissue DEG Table

This table contains one gene-level differential expression result per gene for `{tissue_id}` under model `{model_id}`.

Model:
- backend: `limma/voom`
- formula: `{formula}`
- coefficient tested: `age_mid`

Interpretation:
- positive `logFC` and `stat` mean expression increases with age
- negative `logFC` and `stat` mean expression decreases with age
"""
    write_text(path, text)


def write_run_outputs(
    *,
    run_root: Path,
    model_ids: list[str],
    statuses: list[dict[str, Any]],
    invocation_cmd: list[str],
    prepared_dir: Path,
) -> None:
    fieldnames = [
        "model_id",
        "status",
        "workflow_dir",
        "continuous_metadata_tsv",
        "tissue_deg_tsv",
        "extractor_dir",
        "gmt_path",
        "n_samples",
        "model_formula",
    ]
    write_tsv(run_root / "model_status.tsv", statuses, fieldnames)

    commands_text = "\n".join(
        [
            "# Tissue GMT Run Commands",
            "",
            "```bash",
            shell_join(invocation_cmd),
            "```",
            "",
            f"- prepared_dir: `{prepared_dir}`",
            f"- models: `{','.join(model_ids)}`",
            "",
        ]
    )
    write_text(run_root / "commands.md", commands_text)

    successful = [row for row in statuses if row["status"] == "complete"]
    summary_lines = [
        "# GTEx Tissue GMT Summary",
        "",
        "This run emits one tissue-level GMT per model from a single limma/voom regression fit across all retained tissue samples with continuous age in the model.",
        "",
        f"- requested models: `{len(model_ids)}`",
        f"- completed models: `{len(successful)}`",
        f"- run root: `{run_root}`",
        "",
        "Outputs:",
        "- `model_status.tsv`",
        "- `commands.md`",
        "- `run.log`",
        "",
    ]
    if successful:
        summary_lines.extend(
            [
        "Completed GMT files:",
                *[
                    f"- `{row['model_id']}`: `{row['gmt_path']}`"
                    for row in successful
                ],
            ]
        )
    write_text(run_root / "run_summary.md", "\n".join(summary_lines) + "\n")


def main() -> int:
    args = parse_args()
    repo = repo_root()
    prepared_dir = Path(args.prepared_dir)
    run_root = Path(args.run_root)
    dig_dir = Path(args.dig_dir).resolve()
    manifest_path = Path(args.continuous_age_model_manifest).resolve()
    rscript_bin = resolve_rscript_bin(args.rscript_bin)
    resolved_gtf = resolve_input_path(args.gtf, base_dir=repo)
    model_settings = load_tissue_model_settings(manifest_path)
    model_ids = parse_model_ids(args.model_ids, model_settings)

    if not (prepared_dir / "tissue_counts.tsv").exists() or not (prepared_dir / "sample_metadata.tsv").exists():
        raise SystemExit("prepared_dir must contain tissue_counts.tsv and sample_metadata.tsv")

    needs_gtf = [model_id for model_id in model_ids if model_settings[model_id]["ANNOTATION_MODE"] == "gtf_annotated"]
    if needs_gtf and not resolved_gtf:
        raise SystemExit(f"Models require --gtf: {', '.join(needs_gtf)}")
    if not args.write_commands_only:
        check_r_packages(rscript_bin)

    run_root.mkdir(parents=True, exist_ok=True)
    top_log = run_root / "run.log"
    log_line(top_log, f"[run_gtex_tissue_gmt] tissue_id={args.tissue_id} model_ids={','.join(model_ids)}")

    invocation_cmd = [
        str(repo / "geneset-extractor-dev" / "GTEx" / "run" / "build_genesets.sh"),
        "--tissues",
        args.tissue_id,
        "--models",
        ",".join(model_ids),
    ]
    statuses: list[dict[str, Any]] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(dig_dir / "src")

    for model_id in model_ids:
        settings = model_settings[model_id]
        model_out = run_root / model_id
        workflow_out = model_out / "workflow"
        extractor_out = model_out / "tissue_extractor"
        tissue_deg_tsv = extractor_out / "tissue_deg.tsv"
        continuous_meta_tsv = workflow_out / "continuous_sample_metadata.tsv"
        workflow_script = workflow_out / "run_continuous_age_limma_voom.R"
        model_log = model_out / "run.log"
        model_out.mkdir(parents=True, exist_ok=True)
        log_line(top_log, f"[run_gtex_tissue_gmt] start model={model_id}")

        continuous_meta_summary = prepare_continuous_metadata(prepared_dir, continuous_meta_tsv)
        write_continuous_age_r_script(
            script_path=workflow_script,
            counts_tsv=prepared_dir / "tissue_counts.tsv",
            metadata_tsv=continuous_meta_tsv,
            output_tsv=tissue_deg_tsv,
            include_sex=settings["WORKFLOW_COVARIATES"] != "none",
        )
        write_tissue_deg_note(
            tissue_deg_tsv.with_suffix(".md"),
            args.tissue_id,
            model_id,
            settings["WORKFLOW_COVARIATES"] != "none",
        )
        workflow_cmd = build_workflow_cmd(rscript_bin=rscript_bin, workflow_script=workflow_script)
        extractor_cmd = build_extractor_cmd(
            python_bin=args.python_bin,
            deg_tsv=tissue_deg_tsv,
            extractor_out=extractor_out,
            organism=args.organism,
            genome_build=args.genome_build,
            settings=settings,
            signature_name=f"{model_id}__{args.tissue_id}",
            gtf_path=resolved_gtf,
            provenance_mirror_local_prefix=args.provenance_mirror_local_prefix,
            provenance_mirror_remote_prefix=args.provenance_mirror_remote_prefix,
        )
        write_model_commands(
            model_out=model_out,
            model_id=model_id,
            workflow_cmd=workflow_cmd,
            extractor_cmd=extractor_cmd,
            tissue_deg_tsv=tissue_deg_tsv,
            repo=repo,
            dig_dir=dig_dir,
        )

        status_row: dict[str, Any] = {
            "model_id": model_id,
            "status": "planned" if args.write_commands_only else "running",
            "workflow_dir": str(workflow_out),
            "continuous_metadata_tsv": str(continuous_meta_tsv),
            "tissue_deg_tsv": str(tissue_deg_tsv),
            "extractor_dir": str(extractor_out),
            "gmt_path": str(extractor_out / "genesets.gmt"),
            "n_samples": continuous_meta_summary["n_samples"],
            "model_formula": "age_mid + SEX" if settings["WORKFLOW_COVARIATES"] != "none" else "age_mid",
        }

        if args.write_commands_only:
            statuses.append(status_row)
            continue

        try:
            run_command(workflow_cmd, cwd=repo, env=env, log_path=model_log)
            write_text(tissue_deg_tsv.with_suffix(".log"), f"continuous age workflow completed for {model_id}\n")
            write_tissue_method_note(extractor_out / "naming_reference.md", args.tissue_id, model_id)
            run_command(extractor_cmd, cwd=dig_dir, env=env, log_path=model_log)
            status_row["status"] = "complete"
            log_line(top_log, f"[run_gtex_tissue_gmt] complete model={model_id}")
        except subprocess.CalledProcessError as exc:
            status_row["status"] = f"failed:{exc.returncode}"
            log_line(top_log, f"[run_gtex_tissue_gmt] failed model={model_id} exit_code={exc.returncode}")
            statuses.append(status_row)
            write_run_outputs(
                run_root=run_root,
                model_ids=model_ids,
                statuses=statuses,
                invocation_cmd=invocation_cmd,
                prepared_dir=prepared_dir,
            )
            raise

        statuses.append(status_row)

    write_run_outputs(
        run_root=run_root,
        model_ids=model_ids,
        statuses=statuses,
        invocation_cmd=invocation_cmd,
        prepared_dir=prepared_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
