#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("run_gtex_model_sweep_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_manifest_tsv", required=True)
    parser.add_argument("--reference_gmt_gz", required=True)
    parser.add_argument("--workflow_repo", required=True)
    parser.add_argument("--python_executable", default=sys.executable)
    parser.add_argument("--log_level", default="INFO")
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


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("_") or "item"


def workflow_key(row: pd.Series) -> str:
    covariates = str(row["workflow_covariates"]) if pd.notna(row["workflow_covariates"]) else ""
    covariates_key = covariates if covariates else "none"
    return "__".join(
        [
            f"de={row['workflow_de_mode']}",
            f"balance={row['workflow_balance_groups']}",
            f"seed={row['workflow_balance_seed']}",
            f"scope={row['workflow_gene_filter_scope']}",
            f"covariates={covariates_key}",
            f"backend={row['workflow_backend']}",
        ]
    )


def bash_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def display_optional(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def build_workflow_plan(repo_root: Path, output_dir: Path, model_df: pd.DataFrame) -> pd.DataFrame:
    base_harm_dir = repo_root / "outputs" / "gtex_harmonizome_analysis_v1"
    base_noharm_dir = repo_root / "outputs" / "gtex_no_harmonizome_analysis_v1"

    rows: list[dict[str, object]] = []
    for workflow_name, group_df in model_df.groupby("workflow_name", sort=True):
        row = group_df.iloc[0]
        workflow_slug = sanitize_name(workflow_name)
        execution_priority = int(group_df["execution_priority"].astype(int).min())

        if (
            row["workflow_de_mode"] == "modern"
            and row["workflow_balance_groups"] == "false"
            and row["workflow_balance_seed"] == "0"
            and row["workflow_gene_filter_scope"] == "contrast"
            and str(row["workflow_covariates"]).strip() == "sex,smtsd"
            and row["workflow_backend"] == "lightweight"
        ):
            workflow_source = "reuse_existing_gtex_noharm"
            workflow_dir = base_noharm_dir
            deg_long_tsv = workflow_dir / "combined" / "deg_long_combined.v1.tsv"
            comparison_audit_tsv = workflow_dir / "combined" / "comparison_audit_combined.v1.tsv"
            comparison_manifest_tsv = workflow_dir / "combined" / "comparison_manifest_combined.v1.tsv"
        elif (
            row["workflow_de_mode"] == "harmonizome"
            and row["workflow_balance_groups"] == "true"
            and row["workflow_balance_seed"] == "1"
            and row["workflow_gene_filter_scope"] == "stratum"
            and str(row["workflow_covariates"]).strip() == "sex,smtsd"
            and row["workflow_backend"] == "lightweight"
        ):
            workflow_source = "reuse_existing_gtex_harm"
            workflow_dir = base_harm_dir
            deg_long_tsv = workflow_dir / "combined" / "deg_long_combined.v1.tsv"
            comparison_audit_tsv = workflow_dir / "combined" / "comparison_audit_combined.v1.tsv"
            comparison_manifest_tsv = workflow_dir / "combined" / "comparison_manifest_combined.v1.tsv"
        else:
            workflow_source = "run_new_workflow"
            workflow_dir = output_dir / "workflow_runs" / workflow_name
            deg_long_tsv = workflow_dir / "combined" / "deg_long_combined.v1.tsv"
            comparison_audit_tsv = workflow_dir / "combined" / "comparison_audit_combined.v1.tsv"
            comparison_manifest_tsv = workflow_dir / "combined" / "comparison_manifest_combined.v1.tsv"

        rows.append(
            {
                "workflow_name": workflow_name,
                "workflow_slug": workflow_slug,
                "workflow_source": workflow_source,
                "execution_priority": execution_priority,
                "workflow_de_mode": row["workflow_de_mode"],
                "workflow_balance_groups": row["workflow_balance_groups"],
                "workflow_balance_seed": row["workflow_balance_seed"],
                "workflow_gene_filter_scope": row["workflow_gene_filter_scope"],
                "workflow_covariates": row["workflow_covariates"],
                "workflow_backend": row["workflow_backend"],
                "workflow_dir": str(workflow_dir),
                "deg_long_tsv": str(deg_long_tsv),
                "comparison_audit_tsv": str(comparison_audit_tsv),
                "comparison_manifest_tsv": str(comparison_manifest_tsv),
                "run_script_relpath": f"run/gtex_model_sweep_v1/run_workflow_{workflow_slug}.v1.sh",
                "run_script_md_relpath": f"run/gtex_model_sweep_v1/run_workflow_{workflow_slug}.v1.md",
            }
        )
    workflow_df = pd.DataFrame(rows).sort_values(["execution_priority", "workflow_name"]).reset_index(drop=True)
    LOGGER.info("workflow plan shape=%s", workflow_df.shape)
    return workflow_df


def build_model_plan(output_dir: Path, model_df: pd.DataFrame, workflow_df: pd.DataFrame) -> pd.DataFrame:
    merged_df = model_df.merge(workflow_df, on="workflow_name", how="left", suffixes=("", "_workflow"))
    rows: list[dict[str, object]] = []
    for row in merged_df.to_dict(orient="records"):
        model_name = str(row["model_name"])
        model_dir = output_dir / "models" / model_name
        rows.append(
            {
                **row,
                "model_dir": str(model_dir),
                "generated_gmt_tsv": str(model_dir / "rna_deg_multi.v1" / "genesets.gmt"),
                "legacy_gmt_gz": str(model_dir / "gtex_aging_signatures_legacy_format.v1.gmt.gz"),
                "named_model_gmt_gz": str(model_dir / f"{model_name}.v1.gmt.gz"),
                "comparison_to_reference_tsv": str(model_dir / "comparison_to_reference.v1.tsv"),
                "comparison_to_reference_md": str(model_dir / "comparison_to_reference.v1.md"),
                "provenance_md": str(output_dir / "model_provenance_v1" / f"{model_name}.v1.md"),
                "run_script_relpath": f"run/gtex_model_sweep_v1/run_model_{model_name}.v1.sh",
                "run_script_md_relpath": f"run/gtex_model_sweep_v1/run_model_{model_name}.v1.md",
            }
        )
    planned_df = pd.DataFrame(rows).sort_values(["execution_priority", "model_name"]).reset_index(drop=True)
    LOGGER.info("model plan shape=%s", planned_df.shape)
    return planned_df


def write_workflow_scripts(repo_root: Path, workflow_df: pd.DataFrame) -> list[dict[str, object]]:
    inventory_rows: list[dict[str, object]] = []
    scripts_dir = repo_root / "run" / "gtex_model_sweep_v1"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for row in workflow_df.to_dict(orient="records"):
        script_path = repo_root / str(row["run_script_relpath"])
        script_md_path = repo_root / str(row["run_script_md_relpath"])
        script = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                'repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"',
                "",
                'bash "${repo_root}/run/execute_gtex_model_sweep_workflow.v1.sh" \\',
                f"  --workflow_name {bash_quote(row['workflow_name'])} \\",
                '  --workflow_plan_tsv "${repo_root}/outputs/gtex_model_sweep_v1/workflow_run_plan.v1.tsv" \\',
                '  --output_dir "${repo_root}/outputs/gtex_model_sweep_v1" \\',
                f"  --workflow_repo {bash_quote(str((repo_root / '../../dig-gene-set-extractors').resolve()))} \\",
                '  --resume \\',
                '  "$@"',
                "",
            ]
        )
        write_text(script, script_path)
        script_path.chmod(0o755)
        write_text(
            "\n".join(
                [
                    f"# run_workflow_{row['workflow_slug']}.v1",
                    "",
                    f"Runs one workflow group for `GTEx_model_sweep_v1`.",
                    "",
                    f"- workflow_name: `{row['workflow_name']}`",
                    f"- workflow_source: `{row['workflow_source']}`",
                    f"- output_deg_long_tsv: `{row['deg_long_tsv']}`",
                    "",
                ]
            )
            + "\n",
            script_md_path,
        )
        inventory_rows.append({"script_kind": "workflow", "target_name": row["workflow_name"], "script_path": str(script_path)})
    return inventory_rows


def write_model_scripts(repo_root: Path, model_df: pd.DataFrame) -> list[dict[str, object]]:
    inventory_rows: list[dict[str, object]] = []
    for row in model_df.to_dict(orient="records"):
        script_path = repo_root / str(row["run_script_relpath"])
        script_md_path = repo_root / str(row["run_script_md_relpath"])
        script = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                'repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"',
                "",
                'bash "${repo_root}/run/execute_gtex_model_sweep_model.v1.sh" \\',
                f"  --model_name {bash_quote(row['model_name'])} \\",
                '  --model_run_plan_tsv "${repo_root}/outputs/gtex_model_sweep_v1/model_run_plan.v1.tsv" \\',
                '  --output_dir "${repo_root}/outputs/gtex_model_sweep_v1" \\',
                '  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \\',
                f"  --workflow_repo {bash_quote(str((repo_root / '../../dig-gene-set-extractors').resolve()))} \\",
                '  --resume \\',
                '  "$@"',
                "",
            ]
        )
        write_text(script, script_path)
        script_path.chmod(0o755)
        write_text(
            "\n".join(
                [
                    f"# run_model_{row['model_name']}.v1",
                    "",
                    "Runs one model extraction for `GTEx_model_sweep_v1`.",
                    "",
                    f"- model_name: `{row['model_name']}`",
                    f"- workflow_name: `{row['workflow_name']}`",
                    f"- named_model_gmt_gz: `{row['named_model_gmt_gz']}`",
                    "",
                ]
            )
            + "\n",
            script_md_path,
        )
        inventory_rows.append({"script_kind": "model", "target_name": row["model_name"], "script_path": str(script_path)})
    return inventory_rows


def write_master_script(repo_root: Path, workflow_df: pd.DataFrame, model_df: pd.DataFrame) -> dict[str, object]:
    script_path = repo_root / "run" / "gtex_model_sweep_v1" / "run_all_models.v1.sh"
    script_md_path = repo_root / "run" / "gtex_model_sweep_v1" / "run_all_models.v1.md"
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"',
        "",
        "# Workflow groups",
    ]
    for row in workflow_df.to_dict(orient="records"):
        lines.append(f'bash "${{repo_root}}/{row["run_script_relpath"]}"')
    lines.extend(["", "# Model extractions"])
    for row in model_df.to_dict(orient="records"):
        lines.append(f'bash "${{repo_root}}/{row["run_script_relpath"]}"')
    lines.append("")
    write_text("\n".join(lines), script_path)
    script_path.chmod(0o755)
    write_text(
        "\n".join(
            [
                "# run_all_models.v1",
                "",
                "Runs the full `GTEx_model_sweep_v1` pipeline in two phases:",
                "",
                "1. all distinct workflow groups",
                "2. all model-specific `rna_deg_multi` extractions",
                "",
            ]
        )
        + "\n",
        script_md_path,
    )
    return {"script_kind": "master", "target_name": "all_models", "script_path": str(script_path)}


def write_model_provenance(output_dir: Path, model_df: pd.DataFrame) -> None:
    for row in model_df.to_dict(orient="records"):
        provenance_path = Path(str(row["provenance_md"]))
        covariates = str(row["workflow_covariates"]).strip() or "none"
        extractor_padj_max = display_optional(row["extractor_padj_max"])
        extractor_pvalue_max = display_optional(row["extractor_pvalue_max"])
        extractor_min_abs_logfc = display_optional(row["extractor_min_abs_logfc"])
        extractor_gmt_biotype_allowlist = display_optional(row["extractor_gmt_biotype_allowlist"])
        lines = [
            f"# {row['model_name']} v1",
            "",
            "## Model Identity",
            "",
            f"- model_name: `{row['model_name']}`",
            f"- category: `{row['category']}`",
            f"- model_family: `{row['model_family']}`",
            f"- execution_priority: `{row['execution_priority']}`",
            "",
            "## Design Intent",
            "",
            str(row["design_intent"]),
            "",
            "## Workflow Settings",
            "",
            f"- workflow_name: `{row['workflow_name']}`",
            f"- workflow_source: `{row['workflow_source']}`",
            f"- workflow_de_mode: `{row['workflow_de_mode']}`",
            f"- workflow_balance_groups: `{row['workflow_balance_groups']}`",
            f"- workflow_balance_seed: `{row['workflow_balance_seed']}`",
            f"- workflow_gene_filter_scope: `{row['workflow_gene_filter_scope']}`",
            f"- workflow_covariates: `{covariates}`",
            f"- workflow_backend: `{row['workflow_backend']}`",
            f"- workflow_deg_long_tsv: `{row['deg_long_tsv']}`",
            "",
            "## Extractor Settings",
            "",
            f"- extractor_postprocess_mode: `{row['extractor_postprocess_mode']}`",
            f"- extractor_score_mode: `{row['extractor_score_mode']}`",
            f"- extractor_select: `{row['extractor_select']}`",
            f"- extractor_top_k: `{row['extractor_top_k']}`",
            f"- extractor_padj_max: `{extractor_padj_max}`",
            f"- extractor_pvalue_max: `{extractor_pvalue_max}`",
            f"- extractor_min_abs_logfc: `{extractor_min_abs_logfc}`",
            f"- extractor_gmt_source: `{row['extractor_gmt_source']}`",
            f"- extractor_gmt_topk_list: `{row['extractor_gmt_topk_list']}`",
            f"- extractor_gmt_min_genes: `{row['extractor_gmt_min_genes']}`",
            f"- extractor_gmt_max_genes: `{row['extractor_gmt_max_genes']}`",
            f"- extractor_disable_default_excludes: `{row['extractor_disable_default_excludes']}`",
            f"- extractor_gmt_biotype_allowlist: `{extractor_gmt_biotype_allowlist}`",
            "",
            "## Commands To Run This Model",
            "",
            "Workflow step:",
            "",
            "```bash",
            f"bash {row['run_script_relpath'].replace(f'run_model_{row['model_name']}.v1.sh', f'run_workflow_{row['workflow_slug']}.v1.sh')}",
            "```",
            "",
            "Model extraction step:",
            "",
            "```bash",
            f"bash {row['run_script_relpath']}",
            "```",
            "",
            "## Expected Outputs",
            "",
            f"- named_model_gmt_gz: `{row['named_model_gmt_gz']}`",
            f"- comparison_to_reference_tsv: `{row['comparison_to_reference_tsv']}`",
            f"- comparison_to_reference_md: `{row['comparison_to_reference_md']}`",
            "",
            "## Rationale",
            "",
            str(row["rationale"]),
            "",
        ]
        write_text("\n".join(lines), provenance_path)


def write_plan_docs(output_dir: Path, workflow_df: pd.DataFrame, model_df: pd.DataFrame, script_inventory_df: pd.DataFrame) -> None:
    write_text(
        "\n".join(
            [
                "# Workflow Run Plan v1",
                "",
                f"- workflow_group_count: {int(workflow_df.shape[0])}",
                f"- reused_workflow_groups: {int(workflow_df['workflow_source'].str.startswith('reuse').sum())}",
                f"- new_workflow_groups: {int((workflow_df['workflow_source'] == 'run_new_workflow').sum())}",
                "",
                "This table lists the distinct workflow configurations required by the proposed models and the script path for each workflow group.",
                "",
            ]
        )
        + "\n",
        output_dir / "workflow_run_plan.v1.md",
    )
    write_text(
        "\n".join(
            [
                "# Model Run Plan v1",
                "",
                f"- model_count: {int(model_df.shape[0])}",
                f"- workflow_group_count: {int(workflow_df.shape[0])}",
                "",
                "This table lists one row per proposed model, including the upstream workflow group it depends on, the model-specific extractor settings, and the generated shell script path.",
                "",
            ]
        )
        + "\n",
        output_dir / "model_run_plan.v1.md",
    )
    write_text(
        "\n".join(
            [
                "# Run Script Inventory v1",
                "",
                f"- script_count: {int(script_inventory_df.shape[0])}",
                "",
                "This table inventories the generated workflow, model, and master shell scripts for `GTEx_model_sweep_v1`.",
                "",
            ]
        )
        + "\n",
        output_dir / "run_script_inventory.v1.md",
    )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "run_gtex_model_sweep.v1.log")

    repo_root = output_dir.parent.parent
    model_manifest_tsv = Path(args.model_manifest_tsv).resolve()
    if not model_manifest_tsv.exists():
        raise FileNotFoundError(model_manifest_tsv)

    model_df = pd.read_csv(model_manifest_tsv, sep="\t", dtype=str)
    model_df["workflow_name"] = model_df.apply(workflow_key, axis=1)
    LOGGER.info("loaded model manifest shape=%s", model_df.shape)

    workflow_df = build_workflow_plan(repo_root, output_dir, model_df)
    model_plan_df = build_model_plan(output_dir, model_df, workflow_df)

    workflow_inventory = write_workflow_scripts(repo_root, workflow_df)
    model_inventory = write_model_scripts(repo_root, model_plan_df)
    master_inventory = [write_master_script(repo_root, workflow_df, model_plan_df)]
    script_inventory_df = pd.DataFrame(workflow_inventory + model_inventory + master_inventory)

    write_model_provenance(output_dir, model_plan_df)

    run_summary_df = pd.DataFrame(
        [
            {"metric": "analysis_name", "value": "GTEx_model_sweep_v1"},
            {"metric": "workflow_group_count", "value": int(workflow_df.shape[0])},
            {"metric": "reused_workflow_group_count", "value": int(workflow_df["workflow_source"].str.startswith("reuse").sum())},
            {"metric": "new_workflow_group_count", "value": int((workflow_df["workflow_source"] == "run_new_workflow").sum())},
            {"metric": "model_count", "value": int(model_plan_df.shape[0])},
            {"metric": "generated_script_count", "value": int(script_inventory_df.shape[0])},
        ]
    )

    write_dataframe(workflow_df, output_dir / "workflow_run_plan.v1.tsv")
    write_dataframe(model_plan_df, output_dir / "model_run_plan.v1.tsv")
    write_dataframe(script_inventory_df, output_dir / "run_script_inventory.v1.tsv")
    write_dataframe(run_summary_df, output_dir / "run_summary.v2.tsv")
    write_plan_docs(output_dir, workflow_df, model_plan_df, script_inventory_df)


if __name__ == "__main__":
    main()
