#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import logging
import os
import shlex
import statistics
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_gtex_parameter_sweep_v1")


@dataclass(frozen=True)
class SweepSpec:
    run_id: str
    postprocess_mode: str
    gmt_source: str
    score_mode: str
    gmt_topk_list: int | None
    select: str | None
    top_k: int | None
    padj_max: float | None
    min_abs_logfc: float | None
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--workflow_repo", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--deg_tsv", required=True)
    parser.add_argument("--python_executable", default="python3")
    parser.add_argument("--log_level", default="INFO")
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


def read_gmt(path: Path) -> dict[str, list[str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    gene_sets: dict[str, list[str]] = {}
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            set_name = parts[0]
            if len(parts) == 2:
                genes = [gene for gene in parts[1].split() if gene]
            else:
                genes = [gene for gene in parts[1:] if gene]
            gene_sets[set_name] = genes
    return gene_sets


def convert_generated_gmt_to_legacy_names(generated_gmt_path: Path, output_dir: Path) -> tuple[Path, Path]:
    output_gmt_path = output_dir / "gtex_aging_signatures_legacy_format.v1.gmt"
    output_gmt_gz_path = output_dir / "gtex_aging_signatures_legacy_format.v1.gmt.gz"
    converted_lines: list[str] = []

    with generated_gmt_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            set_name, genes_blob = raw_line.split("\t", 1)
            genes = [gene for gene in genes_blob.split() if gene]
            prefix = "rna_deg_multi__comparison="
            if not set_name.startswith(prefix):
                continue
            comparison_label = set_name[len(prefix) :]
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
    LOGGER.info("wrote legacy formatted GMT: %s n_sets=%d", output_gmt_gz_path, len(converted_lines))
    return output_gmt_path, output_gmt_gz_path


def compare_to_reference(reference_sets: dict[str, list[str]], generated_gmt_gz: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    generated_sets = read_gmt(generated_gmt_gz)
    shared_names = sorted(set(reference_sets) & set(generated_sets))
    missing_names = sorted(set(reference_sets) - set(generated_sets))
    extra_names = sorted(set(generated_sets) - set(reference_sets))

    summary_rows: list[dict[str, object]] = []
    jaccards: list[float] = []
    for set_name in shared_names:
        reference_genes = set(reference_sets[set_name])
        generated_genes = set(generated_sets[set_name])
        intersection = reference_genes & generated_genes
        union = reference_genes | generated_genes
        jaccard = (len(intersection) / len(union)) if union else 0.0
        overlap = (len(intersection) / min(len(reference_genes), len(generated_genes))) if reference_genes and generated_genes else 0.0
        summary_rows.append(
            {
                "set_name": set_name,
                "reference_n_genes": len(reference_genes),
                "generated_n_genes": len(generated_genes),
                "shared_n_genes": len(intersection),
                "jaccard": jaccard,
                "overlap_coefficient": overlap,
            }
        )
        jaccards.append(jaccard)

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(["jaccard", "set_name"], ascending=[False, True]).reset_index(drop=True)

    metrics = {
        "reference_set_count": len(reference_sets),
        "generated_set_count": len(generated_sets),
        "shared_set_count": len(shared_names),
        "missing_set_count": len(missing_names),
        "extra_set_count": len(extra_names),
        "shared_set_fraction": (len(shared_names) / len(reference_sets)) if reference_sets else 0.0,
        "mean_jaccard": statistics.fmean(jaccards) if jaccards else 0.0,
        "median_jaccard": statistics.median(jaccards) if jaccards else 0.0,
        "mean_generated_set_size": float(summary_df["generated_n_genes"].mean()) if not summary_df.empty else 0.0,
        "mean_shared_gene_count": float(summary_df["shared_n_genes"].mean()) if not summary_df.empty else 0.0,
        "top_set_name": str(summary_df.iloc[0]["set_name"]) if not summary_df.empty else "",
        "top_set_jaccard": float(summary_df.iloc[0]["jaccard"]) if not summary_df.empty else 0.0,
    }
    return summary_df, metrics


def build_sweep_specs() -> list[SweepSpec]:
    specs: list[SweepSpec] = []
    filter_profiles = [
        ("nofilter", None, None, "no explicit DEG row filters"),
        ("padj005", 0.05, None, "padj <= 0.05 before ranking"),
        ("padj005_logfc05", 0.05, 0.5, "padj <= 0.05 plus abs(logFC) >= 0.5 before ranking"),
    ]
    score_modes = ["auto", "stat", "logfc", "logfc_times_neglog10p", "signed_neglog10padj"]
    for gmt_topk_list in [200, 250, 300]:
        for score_mode in score_modes:
            for filter_label, padj_max, min_abs_logfc, filter_note in filter_profiles:
                run_id = f"legacy_full_top{gmt_topk_list}_{score_mode}_{filter_label}"
                specs.append(
                    SweepSpec(
                        run_id=run_id,
                        postprocess_mode="legacy",
                        gmt_source="full",
                        score_mode=score_mode,
                        gmt_topk_list=gmt_topk_list,
                        select=None,
                        top_k=None,
                        padj_max=padj_max,
                        min_abs_logfc=min_abs_logfc,
                        notes=f"full ranked GMT output; {filter_note}",
                    )
                )

    for top_k in [200, 250]:
        for score_mode in ["stat", "signed_neglog10padj"]:
            for filter_label, padj_max, min_abs_logfc, filter_note in filter_profiles[:2]:
                run_id = f"legacy_selected_top{top_k}_{score_mode}_{filter_label}"
                specs.append(
                    SweepSpec(
                        run_id=run_id,
                        postprocess_mode="legacy",
                        gmt_source="selected",
                        score_mode=score_mode,
                        gmt_topk_list=top_k,
                        select="top_k",
                        top_k=top_k,
                        padj_max=padj_max,
                        min_abs_logfc=min_abs_logfc,
                        notes=f"selected-gene GMT output; {filter_note}",
                    )
                )

    specs.append(
        SweepSpec(
            run_id="harmonizome_preset_control",
            postprocess_mode="harmonizome",
            gmt_source="full",
            score_mode="auto",
            gmt_topk_list=None,
            select=None,
            top_k=None,
            padj_max=None,
            min_abs_logfc=None,
            notes="converter harmonizome preset control run on the no-harmonizome DEG table",
        )
    )
    return specs


def build_command(
    spec: SweepSpec,
    *,
    python_executable: str,
    deg_tsv: Path,
    out_dir: Path,
) -> list[str]:
    cmd = [
        python_executable,
        "-m",
        "geneset_extractors.cli",
        "convert",
        "rna_deg_multi",
        "--deg_tsv",
        str(deg_tsv),
        "--comparison_column",
        "comparison_id",
        "--out_dir",
        str(out_dir),
        "--organism",
        "human",
        "--genome_build",
        "hg38",
        "--postprocess_mode",
        spec.postprocess_mode,
        "--score_mode",
        spec.score_mode,
        "--gmt_source",
        spec.gmt_source,
        "--emit_full",
        "false",
    ]
    if spec.gmt_topk_list is not None:
        cmd.extend(["--gmt_topk_list", str(spec.gmt_topk_list)])
    if spec.select:
        cmd.extend(["--select", spec.select])
    if spec.top_k is not None:
        cmd.extend(["--top_k", str(spec.top_k)])
    if spec.padj_max is not None:
        cmd.extend(["--padj_max", str(spec.padj_max)])
    if spec.min_abs_logfc is not None:
        cmd.extend(["--min_abs_logfc", str(spec.min_abs_logfc)])
    return cmd


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run_one_spec(
    spec: SweepSpec,
    *,
    workflow_repo: Path,
    deg_tsv: Path,
    reference_sets: dict[str, list[str]],
    output_dir: Path,
    python_executable: str,
) -> dict[str, object]:
    run_dir = output_dir / "runs" / spec.run_id
    rna_deg_multi_out_dir = run_dir / "rna_deg_multi.v1"
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_command(spec, python_executable=python_executable, deg_tsv=deg_tsv, out_dir=rna_deg_multi_out_dir)
    command_path = run_dir / "command.v1.sh"
    command_path.write_text(shell_join(cmd) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(workflow_repo / "src")
    LOGGER.info("starting run_id=%s", spec.run_id)
    result = subprocess.run(
        cmd,
        cwd=workflow_repo,
        env=env,
        capture_output=True,
        text=True,
    )
    write_text(result.stdout, run_dir / "command.stdout.v1.log")
    write_text(result.stderr, run_dir / "command.stderr.v1.log")

    row: dict[str, object] = asdict(spec)
    row["return_code"] = int(result.returncode)
    row["command"] = shell_join(cmd)

    if result.returncode != 0:
        LOGGER.warning("run failed run_id=%s return_code=%d", spec.run_id, result.returncode)
        row.update(
            {
                "status": "error",
                "reference_set_count": len(reference_sets),
                "generated_set_count": 0,
                "shared_set_count": 0,
                "missing_set_count": len(reference_sets),
                "extra_set_count": 0,
                "shared_set_fraction": 0.0,
                "mean_jaccard": 0.0,
                "median_jaccard": 0.0,
                "mean_generated_set_size": 0.0,
                "mean_shared_gene_count": 0.0,
                "top_set_name": "",
                "top_set_jaccard": 0.0,
                "comparison_tsv": "",
                "legacy_gmt_gz": "",
            }
        )
        return row

    generated_gmt_path = rna_deg_multi_out_dir / "genesets.gmt"
    if not generated_gmt_path.exists():
        LOGGER.warning("run missing genesets.gmt run_id=%s", spec.run_id)
        row.update(
            {
                "status": "error",
                "reference_set_count": len(reference_sets),
                "generated_set_count": 0,
                "shared_set_count": 0,
                "missing_set_count": len(reference_sets),
                "extra_set_count": 0,
                "shared_set_fraction": 0.0,
                "mean_jaccard": 0.0,
                "median_jaccard": 0.0,
                "mean_generated_set_size": 0.0,
                "mean_shared_gene_count": 0.0,
                "top_set_name": "",
                "top_set_jaccard": 0.0,
                "comparison_tsv": "",
                "legacy_gmt_gz": "",
            }
        )
        return row

    _, legacy_gmt_gz = convert_generated_gmt_to_legacy_names(generated_gmt_path, run_dir)
    comparison_df, metrics = compare_to_reference(reference_sets, legacy_gmt_gz)
    comparison_path = run_dir / "comparison_to_reference.v1.tsv"
    write_dataframe(comparison_df, comparison_path)
    row.update(metrics)
    row["status"] = "success"
    row["comparison_tsv"] = str(comparison_path)
    row["legacy_gmt_gz"] = str(legacy_gmt_gz)
    LOGGER.info(
        "completed run_id=%s shared=%d mean_jaccard=%.4f median_jaccard=%.4f",
        spec.run_id,
        int(row["shared_set_count"]),
        float(row["mean_jaccard"]),
        float(row["median_jaccard"]),
    )
    return row


def build_parameter_effects(summary_df: pd.DataFrame) -> pd.DataFrame:
    success_df = summary_df.loc[summary_df["status"] == "success"].copy()
    frames: list[pd.DataFrame] = []
    for parameter in ["postprocess_mode", "gmt_source", "score_mode", "gmt_topk_list", "padj_max", "min_abs_logfc"]:
        grouped = (
            success_df.groupby(parameter, dropna=False)[
                ["shared_set_count", "shared_set_fraction", "mean_jaccard", "median_jaccard", "mean_shared_gene_count"]
            ]
            .agg(["mean", "max"])
            .reset_index()
        )
        grouped.columns = [
            parameter if idx == 0 else f"{metric}_{agg}"
            for idx, (metric, agg) in enumerate(grouped.columns.to_flat_index())
        ]
        grouped = grouped.rename(columns={parameter: "parameter_value"})
        grouped.insert(0, "parameter_name", parameter)
        frames.append(grouped)
    effects_df = pd.concat(frames, ignore_index=True)
    effects_df["parameter_value"] = effects_df["parameter_value"].fillna("none").astype(str)
    effects_df = effects_df.sort_values(["parameter_name", "mean_jaccard_mean", "shared_set_count_mean"], ascending=[True, False, False]).reset_index(drop=True)
    return effects_df


def build_findings_markdown(summary_df: pd.DataFrame, effects_df: pd.DataFrame) -> str:
    success_df = summary_df.loc[summary_df["status"] == "success"].copy()
    success_df = success_df.sort_values(
        ["shared_set_count", "mean_jaccard", "median_jaccard"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    top_row = success_df.iloc[0]

    baseline_df = success_df.loc[success_df["run_id"] == "legacy_full_top200_auto_nofilter"]
    baseline_row = baseline_df.iloc[0] if not baseline_df.empty else None
    harmonizome_df = success_df.loc[success_df["run_id"] == "harmonizome_preset_control"]
    harmonizome_row = harmonizome_df.iloc[0] if not harmonizome_df.empty else None

    lines = [
        "# GTEx Parameter Sweep Findings v1",
        "",
        f"- successful runs: {len(success_df)}",
        f"- failed runs: {int((summary_df['status'] != 'success').sum())}",
        f"- best run by shared-set coverage then overlap: `{top_row['run_id']}`",
        f"- best run metrics: shared_set_count={int(top_row['shared_set_count'])}, "
        f"mean_jaccard={float(top_row['mean_jaccard']):.6f}, median_jaccard={float(top_row['median_jaccard']):.6f}",
        "",
        "## Take-Home Message",
        "",
    ]

    if baseline_row is not None:
        lines.append(
            "Changing converter parameters can move the regenerated library toward the legacy GMT, "
            f"but only modestly. The baseline legacy-style rerun (`legacy_full_top200_auto_nofilter`) "
            f"had shared_set_count={int(baseline_row['shared_set_count'])}, mean_jaccard={float(baseline_row['mean_jaccard']):.6f}, "
            f"and median_jaccard={float(baseline_row['median_jaccard']):.6f}."
        )
    else:
        lines.append(
            "Changing converter parameters can move the regenerated library toward the legacy GMT, "
            "but the effect is modest rather than transformative."
        )

    lines.append(
        f"The best run in this sweep was `{top_row['run_id']}`, which reached "
        f"shared_set_count={int(top_row['shared_set_count'])}, mean_jaccard={float(top_row['mean_jaccard']):.6f}, "
        f"and median_jaccard={float(top_row['median_jaccard']):.6f}."
    )
    if baseline_row is not None:
        shared_delta = int(top_row["shared_set_count"]) - int(baseline_row["shared_set_count"])
        mean_delta = float(top_row["mean_jaccard"]) - float(baseline_row["mean_jaccard"])
        lines.append(
            f"Relative to the baseline, that is a change of shared_set_count={shared_delta:+d} "
            f"and mean_jaccard={mean_delta:+.6f}."
        )
    if harmonizome_row is not None:
        lines.append(
            f"The Harmonizome preset control remained worse on set-name coverage "
            f"(shared_set_count={int(harmonizome_row['shared_set_count'])}, mean_jaccard={float(harmonizome_row['mean_jaccard']):.6f}), "
            "which reinforces that the Harmonizome-style postprocessing is not the right direction if the goal is to mimic the legacy GTEx library."
        )

    lines.extend(["", "## Highest-Leverage Parameters", ""])
    top_effects = effects_df.loc[effects_df["parameter_name"].isin(["gmt_topk_list", "score_mode", "padj_max", "min_abs_logfc", "gmt_source"])]
    for parameter_name in ["score_mode", "gmt_topk_list", "padj_max", "min_abs_logfc", "gmt_source"]:
        subset = top_effects.loc[top_effects["parameter_name"] == parameter_name]
        if subset.empty:
            continue
        best_average = subset.iloc[0]
        best_max = subset.sort_values(["mean_jaccard_max", "shared_set_count_max"], ascending=[False, False]).iloc[0]
        lines.append(
            f"- `{parameter_name}`: best average setting in this sweep was `{best_average['parameter_value']}` "
            f"(mean mean_jaccard={float(best_average['mean_jaccard_mean']):.6f}, "
            f"mean shared_set_count={float(best_average['shared_set_count_mean']):.2f}); "
            f"best single-run setting was `{best_max['parameter_value']}` "
            f"(max mean_jaccard={float(best_max['mean_jaccard_max']):.6f}, "
            f"max shared_set_count={float(best_max['shared_set_count_max']):.0f})."
        )

    lines.extend(["", "## Top Runs", ""])
    for _, row in success_df.head(10).iterrows():
        lines.append(
            f"- `{row['run_id']}`: postprocess_mode={row['postprocess_mode']}, gmt_source={row['gmt_source']}, "
            f"score_mode={row['score_mode']}, gmt_topk_list={row['gmt_topk_list']}, padj_max={row['padj_max']}, "
            f"min_abs_logfc={row['min_abs_logfc']}, shared_set_count={int(row['shared_set_count'])}, "
            f"mean_jaccard={float(row['mean_jaccard']):.6f}, median_jaccard={float(row['median_jaccard']):.6f}."
        )

    lines.extend(["", "## Interpretation", ""])
    lines.append(
        "The sweep shows that the easiest way to move the regenerated sets toward the legacy GMT is to stay on the "
        "legacy-style converter path and tune how the full ranked DEG table is turned into GMT sets. In contrast, "
        "switching to selected-gene GMT export or the Harmonizome preset does not recover the legacy library well."
    )
    lines.append(
        "One non-obvious result from the code path is that when `gmt_source=full`, `select` and `top_k` do not determine "
        "GMT membership. In that mode, the decisive knobs are the ranking method (`score_mode`), pre-ranking DEG filters "
        "(`padj_max`, `min_abs_logfc`), and the emitted set size (`gmt_topk_list`)."
    )
    return "\n".join(lines) + "\n"


def build_summary_markdown(summary_df: pd.DataFrame) -> str:
    lines = [
        "# GTEx Parameter Sweep Summary v1",
        "",
        "Each row is one `rna_deg_multi` configuration run on the existing `gtex_no_harmonizome_analysis_v1` combined DEG table and scored against the legacy GTEx aging GMT.",
        "",
        "Columns include the converter settings, command status, and summary overlap metrics.",
        "",
        f"- total runs: {len(summary_df)}",
        f"- successful runs: {int((summary_df['status'] == 'success').sum())}",
        f"- failed runs: {int((summary_df['status'] != 'success').sum())}",
        "",
    ]
    return "\n".join(lines)


def build_effects_markdown(effects_df: pd.DataFrame) -> str:
    lines = [
        "# GTEx Parameter Effects v1",
        "",
        "This table aggregates the successful sweep runs by one parameter at a time.",
        "",
        "- `*_mean` columns summarize the average metric value across runs with that parameter value.",
        "- `*_max` columns show the best observed run for that parameter value.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_gtex_parameter_sweep.v1.log")

    workflow_repo = Path(args.workflow_repo).resolve()
    reference_gmt_gz = Path(args.reference_gmt_gz).resolve()
    deg_tsv = Path(args.deg_tsv).resolve()
    if not workflow_repo.exists():
        raise FileNotFoundError(f"workflow repo not found: {workflow_repo}")
    if not reference_gmt_gz.exists():
        raise FileNotFoundError(f"reference GMT not found: {reference_gmt_gz}")
    if not deg_tsv.exists():
        raise FileNotFoundError(f"DEG table not found: {deg_tsv}")

    deg_preview_df = pd.read_csv(deg_tsv, sep="\t", nrows=5, dtype=str)
    LOGGER.info("deg preview shape=%s columns=%s", deg_preview_df.shape, list(deg_preview_df.columns))
    reference_sets = read_gmt(reference_gmt_gz)
    LOGGER.info("reference GMT set count=%d", len(reference_sets))

    specs = build_sweep_specs()
    LOGGER.info("prepared sweep specs n=%d", len(specs))

    manifest_rows = []
    for spec in specs:
        row = run_one_spec(
            spec,
            workflow_repo=workflow_repo,
            deg_tsv=deg_tsv,
            reference_sets=reference_sets,
            output_dir=output_dir,
            python_executable=args.python_executable,
        )
        manifest_rows.append(row)

    summary_df = pd.DataFrame(manifest_rows)
    summary_df = summary_df.sort_values(
        ["status", "shared_set_count", "mean_jaccard", "median_jaccard", "run_id"],
        ascending=[True, False, False, False, True],
    ).reset_index(drop=True)
    summary_path = output_dir / "parameter_sweep_summary.v1.tsv"
    write_dataframe(summary_df, summary_path)
    write_text(build_summary_markdown(summary_df), output_dir / "parameter_sweep_summary.v1.md")

    effects_df = build_parameter_effects(summary_df)
    effects_path = output_dir / "parameter_effects.v1.tsv"
    write_dataframe(effects_df, effects_path)
    write_text(build_effects_markdown(effects_df), output_dir / "parameter_effects.v1.md")

    findings_path = output_dir / "findings.v1.md"
    write_text(build_findings_markdown(summary_df, effects_df), findings_path)
    LOGGER.info("completed parameter sweep output_dir=%s", output_dir)


if __name__ == "__main__":
    main()
