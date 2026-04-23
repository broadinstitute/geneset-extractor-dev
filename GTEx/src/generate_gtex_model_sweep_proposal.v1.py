#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("generate_gtex_model_sweep_proposal_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", required=True)
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


def add_model(
    rows: list[dict[str, object]],
    *,
    model_name: str,
    category: str,
    model_family: str,
    execution_priority: int,
    design_intent: str,
    workflow_de_mode: str,
    workflow_balance_groups: bool,
    workflow_balance_seed: int,
    workflow_gene_filter_scope: str,
    workflow_covariates: str,
    workflow_backend: str,
    extractor_postprocess_mode: str,
    extractor_score_mode: str,
    extractor_select: str,
    extractor_top_k: int,
    extractor_padj_max: str,
    extractor_pvalue_max: str,
    extractor_min_abs_logfc: str,
    extractor_gmt_source: str,
    extractor_gmt_topk_list: str,
    extractor_gmt_min_genes: int,
    extractor_gmt_max_genes: int,
    extractor_disable_default_excludes: bool,
    extractor_gmt_biotype_allowlist: str,
    rationale: str,
) -> None:
    rows.append(
        {
            "analysis_name": "GTEx_model_sweep_v1",
            "model_name": model_name,
            "category": category,
            "model_family": model_family,
            "execution_priority": execution_priority,
            "design_intent": design_intent,
            "workflow_de_mode": workflow_de_mode,
            "workflow_balance_groups": str(bool(workflow_balance_groups)).lower(),
            "workflow_balance_seed": workflow_balance_seed,
            "workflow_gene_filter_scope": workflow_gene_filter_scope,
            "workflow_covariates": workflow_covariates,
            "workflow_backend": workflow_backend,
            "extractor_postprocess_mode": extractor_postprocess_mode,
            "extractor_score_mode": extractor_score_mode,
            "extractor_select": extractor_select,
            "extractor_top_k": extractor_top_k,
            "extractor_padj_max": extractor_padj_max,
            "extractor_pvalue_max": extractor_pvalue_max,
            "extractor_min_abs_logfc": extractor_min_abs_logfc,
            "extractor_gmt_source": extractor_gmt_source,
            "extractor_gmt_topk_list": extractor_gmt_topk_list,
            "extractor_gmt_min_genes": extractor_gmt_min_genes,
            "extractor_gmt_max_genes": extractor_gmt_max_genes,
            "extractor_disable_default_excludes": str(bool(extractor_disable_default_excludes)).lower(),
            "extractor_gmt_biotype_allowlist": extractor_gmt_biotype_allowlist,
            "rationale": rationale,
        }
    )


def build_model_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    # Anchor models
    add_model(
        rows,
        model_name="current_repo_default_harm",
        category="anchor",
        model_family="current_defaults",
        execution_priority=1,
        design_intent="Current default stack in the extractor repo: modern DE workflow plus harmonizome extractor defaults.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="sex,smtsd",
        workflow_backend="auto",
        extractor_postprocess_mode="harmonizome",
        extractor_score_mode="auto",
        extractor_select="top_k",
        extractor_top_k=200,
        extractor_padj_max="",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=5,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="",
        rationale="Anchors the sweep to the current repo defaults documented for rna_de_prepare and rna_deg_multi.",
    )
    add_model(
        rows,
        model_name="current_gtex_noharm_legacy200",
        category="anchor",
        model_family="current_gtex_baselines",
        execution_priority=2,
        design_intent="Current GTEx no-harmonizome baseline used in the existing GTEx rerun.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="auto",
        extractor_select="top_k",
        extractor_top_k=200,
        extractor_padj_max="",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="full",
        extractor_gmt_topk_list="200",
        extractor_gmt_min_genes=100,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Matches the existing gtex_no_harmonizome_analysis_v1 baseline and should be retained as the main comparator.",
    )
    add_model(
        rows,
        model_name="current_gtex_harm_signed250",
        category="anchor",
        model_family="current_gtex_baselines",
        execution_priority=3,
        design_intent="Current GTEx harmonizome-style baseline used in the existing GTEx rerun.",
        workflow_de_mode="harmonizome",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="harmonizome",
        extractor_score_mode="signed_neglog10padj",
        extractor_select="threshold",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=5,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=True,
        extractor_gmt_biotype_allowlist="all",
        rationale="Anchors the sweep to the existing harmonizome-style GTEx run that is closer to published Harmonizome behavior.",
    )

    # Focused parameter sweeps around the legacy-style baseline
    for model_name, top_k, rationale in [
        ("legacy_top100", 100, "Tests a more compact legacy-style set size."),
        ("legacy_top150", 150, "Tests whether a slightly smaller library reduces diffuse membership."),
        ("legacy_top250", 250, "Tests direct size alignment to the 250-gene legacy GMT convention."),
        ("legacy_top300", 300, "Tests whether a mildly broader library recovers legacy genes missed at top 200."),
    ]:
        add_model(
            rows,
            model_name=model_name,
            category="parameter_sweep",
            model_family="legacy_size_sweep",
            execution_priority=10,
            design_intent="Legacy-style ranking with only the selected set size varied.",
            workflow_de_mode="modern",
            workflow_balance_groups=False,
            workflow_balance_seed=0,
            workflow_gene_filter_scope="contrast",
            workflow_covariates="sex,smtsd",
            workflow_backend="lightweight",
            extractor_postprocess_mode="legacy",
            extractor_score_mode="auto",
            extractor_select="top_k",
            extractor_top_k=top_k,
            extractor_padj_max="",
            extractor_pvalue_max="",
            extractor_min_abs_logfc="",
            extractor_gmt_source="full",
            extractor_gmt_topk_list=str(top_k),
            extractor_gmt_min_genes=100,
            extractor_gmt_max_genes=500,
            extractor_disable_default_excludes=False,
            extractor_gmt_biotype_allowlist="protein_coding",
            rationale=rationale,
        )

    for model_name, score_mode, rationale in [
        ("legacy_stat200", "stat", "Tests direct use of the model statistic instead of auto mode."),
        ("legacy_signedfdr200", "signed_neglog10padj", "Tests FDR-driven directional ranking without switching to harmonizome mode."),
        ("legacy_signedp200", "signed_neglog10pvalue", "Tests raw-p directional ranking after aggregation."),
        ("legacy_logfcp200", "logfc_times_neglog10p", "Tests hybrid effect-size-plus-significance ranking."),
        ("legacy_logfc200", "logfc", "Tests effect-size-first ranking without changing the DE fit."),
    ]:
        add_model(
            rows,
            model_name=model_name,
            category="parameter_sweep",
            model_family="legacy_score_sweep",
            execution_priority=11,
            design_intent="Legacy-style selection with the ranking rule varied while preserving the same DE workflow.",
            workflow_de_mode="modern",
            workflow_balance_groups=False,
            workflow_balance_seed=0,
            workflow_gene_filter_scope="contrast",
            workflow_covariates="sex,smtsd",
            workflow_backend="lightweight",
            extractor_postprocess_mode="legacy",
            extractor_score_mode=score_mode,
            extractor_select="top_k",
            extractor_top_k=200,
            extractor_padj_max="",
            extractor_pvalue_max="",
            extractor_min_abs_logfc="",
            extractor_gmt_source="full",
            extractor_gmt_topk_list="200",
            extractor_gmt_min_genes=100,
            extractor_gmt_max_genes=500,
            extractor_disable_default_excludes=False,
            extractor_gmt_biotype_allowlist="protein_coding",
            rationale=rationale,
        )

    for model_name, padj_max, min_abs_logfc, rationale in [
        ("legacy_signedfdr005", "0.05", "", "Tests explicit FDR gating before legacy-style aggregation."),
        ("legacy_signedfdr005_logfc025", "0.05", "0.25", "Tests significance plus moderate effect-size gating."),
        ("legacy_signedfdr005_logfc050", "0.05", "0.50", "Tests significance plus stronger effect-size gating."),
    ]:
        add_model(
            rows,
            model_name=model_name,
            category="parameter_sweep",
            model_family="legacy_filter_sweep",
            execution_priority=12,
            design_intent="Legacy-style extraction with explicit significance/effect-size row filters.",
            workflow_de_mode="modern",
            workflow_balance_groups=False,
            workflow_balance_seed=0,
            workflow_gene_filter_scope="contrast",
            workflow_covariates="sex,smtsd",
            workflow_backend="lightweight",
            extractor_postprocess_mode="legacy",
            extractor_score_mode="signed_neglog10padj",
            extractor_select="top_k",
            extractor_top_k=200,
            extractor_padj_max=padj_max,
            extractor_pvalue_max="",
            extractor_min_abs_logfc=min_abs_logfc,
            extractor_gmt_source="full",
            extractor_gmt_topk_list="200",
            extractor_gmt_min_genes=100,
            extractor_gmt_max_genes=500,
            extractor_disable_default_excludes=False,
            extractor_gmt_biotype_allowlist="protein_coding",
            rationale=rationale,
        )

    # Defensible alternative workflow designs
    add_model(
        rows,
        model_name="modern_stratum_legacy200",
        category="defensible_models",
        model_family="gene_filter_scope",
        execution_priority=20,
        design_intent="Use all available samples but filter genes at the stratum level to stabilize feature inclusion across age contrasts.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="auto",
        extractor_select="top_k",
        extractor_top_k=200,
        extractor_padj_max="",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="full",
        extractor_gmt_topk_list="200",
        extractor_gmt_min_genes=100,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Separates the effect of gene-filter scope from the effect of group balancing.",
    )
    add_model(
        rows,
        model_name="modern_balanced_legacy200",
        category="defensible_models",
        model_family="sample_balancing",
        execution_priority=21,
        design_intent="Apply deterministic case-control balancing in modern mode without switching the whole workflow to harmonizome mode.",
        workflow_de_mode="modern",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="auto",
        extractor_select="top_k",
        extractor_top_k=200,
        extractor_padj_max="",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="full",
        extractor_gmt_topk_list="200",
        extractor_gmt_min_genes=100,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Isolates whether deterministic balancing itself materially changes gene inclusion.",
    )
    add_model(
        rows,
        model_name="modern_nocovariates_legacy200",
        category="defensible_models",
        model_family="covariate_design",
        execution_priority=22,
        design_intent="Remove fixed-effect covariates to test whether current covariate adjustment is suppressing real signal.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="auto",
        extractor_select="top_k",
        extractor_top_k=200,
        extractor_padj_max="",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="full",
        extractor_gmt_topk_list="200",
        extractor_gmt_min_genes=100,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Tests whether sex and tissue-subsite adjustment is materially reducing age-associated ranking signal.",
    )
    add_model(
        rows,
        model_name="modern_sex_only_legacy200",
        category="defensible_models",
        model_family="covariate_design",
        execution_priority=23,
        design_intent="Use sex as the only fixed-effect nuisance covariate.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="sex",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="auto",
        extractor_select="top_k",
        extractor_top_k=200,
        extractor_padj_max="",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="full",
        extractor_gmt_topk_list="200",
        extractor_gmt_min_genes=100,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Separates the impact of sex adjustment from the impact of tissue-subsite adjustment.",
    )
    add_model(
        rows,
        model_name="harm_signedfdr250_limma",
        category="defensible_models",
        model_family="backend_validation",
        execution_priority=24,
        design_intent="Harmonizome-style DE plus an explicit limma/voom backend for a statistically closer benchmark run.",
        workflow_de_mode="harmonizome",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="r_limma_voom",
        extractor_postprocess_mode="harmonizome",
        extractor_score_mode="signed_neglog10padj",
        extractor_select="threshold",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=5,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=True,
        extractor_gmt_biotype_allowlist="all",
        rationale="Tests whether the lightweight backend is a material source of divergence from legacy Harmonizome behavior.",
    )
    add_model(
        rows,
        model_name="harm_stat250_limma",
        category="defensible_models",
        model_family="backend_validation",
        execution_priority=25,
        design_intent="Harmonizome-style DE but rank with the model statistic rather than FDR alone.",
        workflow_de_mode="harmonizome",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="r_limma_voom",
        extractor_postprocess_mode="harmonizome",
        extractor_score_mode="stat",
        extractor_select="threshold",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=5,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=True,
        extractor_gmt_biotype_allowlist="all",
        rationale="Tests whether ranking by moderated statistic after harmonizome-style filtering better recovers legacy membership.",
    )
    add_model(
        rows,
        model_name="harm_signedfdr250_pcoding",
        category="defensible_models",
        model_family="annotation_filters",
        execution_priority=26,
        design_intent="Keep harmonizome-style DE and ranking but restore a protein-coding bias in the emitted GMT.",
        workflow_de_mode="harmonizome",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="harmonizome",
        extractor_score_mode="signed_neglog10padj",
        extractor_select="threshold",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=5,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=True,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Tests whether legacy mismatch is driven partly by harmonizome-mode inclusion of non-protein-coding genes.",
    )
    add_model(
        rows,
        model_name="harm_signedfdr250_default_excludes",
        category="defensible_models",
        model_family="annotation_filters",
        execution_priority=27,
        design_intent="Keep harmonizome-style DE and ranking but re-enable default technical gene-family excludes.",
        workflow_de_mode="harmonizome",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="harmonizome",
        extractor_score_mode="signed_neglog10padj",
        extractor_select="threshold",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=5,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="all",
        rationale="Tests whether harmonizome-mode technical-family inclusions are diluting biological specificity.",
    )
    add_model(
        rows,
        model_name="harm_logfc_fdr005_top250",
        category="defensible_models",
        model_family="effect_size_models",
        execution_priority=28,
        design_intent="Harmonizome-style DE with explicit FDR gating, then rank within the retained rows by logFC.",
        workflow_de_mode="harmonizome",
        workflow_balance_groups=True,
        workflow_balance_seed=1,
        workflow_gene_filter_scope="stratum",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="logfc",
        extractor_select="top_k",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="0.25",
        extractor_gmt_source="full",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=25,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Captures a defensible effect-size-first alternative after conservative significance filtering.",
    )
    add_model(
        rows,
        model_name="modern_signedfdr250_selected",
        category="defensible_models",
        model_family="hybrid_library_models",
        execution_priority=29,
        design_intent="Use all-samples modern DE but harmonizome-like directional FDR ranking and selected-source GMT emission.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="signed_neglog10padj",
        extractor_select="top_k",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=25,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Separates harmonizome-like ranking/export behavior from harmonizome-mode DE fitting.",
    )
    add_model(
        rows,
        model_name="modern_signedp250_selected",
        category="defensible_models",
        model_family="hybrid_library_models",
        execution_priority=30,
        design_intent="Use all-samples modern DE with raw-p directional ranking and selected-source GMT export.",
        workflow_de_mode="modern",
        workflow_balance_groups=False,
        workflow_balance_seed=0,
        workflow_gene_filter_scope="contrast",
        workflow_covariates="sex,smtsd",
        workflow_backend="lightweight",
        extractor_postprocess_mode="legacy",
        extractor_score_mode="signed_neglog10pvalue",
        extractor_select="top_k",
        extractor_top_k=250,
        extractor_padj_max="0.05",
        extractor_pvalue_max="",
        extractor_min_abs_logfc="",
        extractor_gmt_source="selected",
        extractor_gmt_topk_list="250",
        extractor_gmt_min_genes=25,
        extractor_gmt_max_genes=500,
        extractor_disable_default_excludes=False,
        extractor_gmt_biotype_allowlist="protein_coding",
        rationale="Tests whether raw p-value ordering within an FDR-filtered set better preserves subtle age-associated rankings.",
    )
    return rows


def build_markdown(model_df: pd.DataFrame, family_df: pd.DataFrame) -> str:
    anchor_df = model_df.loc[model_df["category"] == "anchor"].copy()
    sweep_df = model_df.loc[model_df["category"] == "parameter_sweep"].copy()
    defensible_df = model_df.loc[model_df["category"] == "defensible_models"].copy()

    lines = [
        "# GTEx Model Sweep Proposal v1",
        "",
        "## Objective",
        "",
        "This proposal defines step 1 of `GTEx_model_sweep_v1`: a concrete, versioned model catalog for generating multiple GTEx aging-signature GMT libraries from `dig-gene-set-extractors`.",
        "The proposal is grounded in the current extractor CLI and RNA-seq guidance, and separates three concerns that can change final gene inclusion:",
        "",
        "- upstream DE fitting choices in `workflows rna_de_prepare`",
        "- downstream row filtering, ranking, and GMT emission choices in `convert rna_deg_multi`",
        "- annotation and technical-gene inclusion rules that can change which genes survive to the final GMT",
        "",
        "## Current Anchor Models",
        "",
        "These models should be kept in the sweep even if additional models are added later, because they anchor interpretation against current behavior.",
        "",
    ]
    for row in anchor_df.sort_values(["execution_priority", "model_name"]).to_dict(orient="records"):
        lines.append(
            f"- `{row['model_name']}`: {row['design_intent']} "
            f"Workflow=`{row['workflow_de_mode']}`, backend=`{row['workflow_backend']}`, "
            f"extractor=`{row['extractor_postprocess_mode']}`, score=`{row['extractor_score_mode']}`."
        )

    lines.extend(
        [
            "",
            "## Step 1i: Parameter-Sweep Models",
            "",
            f"- proposed parameter-sweep model count: {int(sweep_df.shape[0])}",
            "",
            "These models vary a small number of parameters around the current GTEx baselines so that any change in GMT membership can be attributed to a specific knob.",
            "",
        ]
    )
    for row in family_df.loc[family_df["category"] == "parameter_sweep"].sort_values("model_count").to_dict(orient="records"):
        lines.append(
            f"- `{row['model_family']}`: {int(row['model_count'])} models. "
            f"Representative intent: {row['family_rationale']}"
        )

    lines.extend(
        [
            "",
            "Most important sweep axes for gene inclusion:",
            "",
            "- set size via `top_k` and `gmt_topk_list`",
            "- ranking mode via `score_mode`",
            "- explicit row filters via `padj_max`, `pvalue_max`, and `min_abs_logfc`",
            "- GMT source via full ranked table versus selected rows",
            "",
            "## Step 1ii: Defensible Alternative Models",
            "",
            f"- proposed defensible-model count: {int(defensible_df.shape[0])}",
            "",
            "These models are not just knob turns. Each one reflects a defensible methodological stance about how RNA DE signatures should be produced for GTEx-like observational tissue data.",
            "",
        ]
    )
    for row in family_df.loc[family_df["category"] == "defensible_models"].sort_values("model_count").to_dict(orient="records"):
        lines.append(
            f"- `{row['model_family']}`: {int(row['model_count'])} models. "
            f"Representative intent: {row['family_rationale']}"
        )

    lines.extend(
        [
            "",
            "## Recommended Execution Order",
            "",
            "Run the models in four phases so the early results can prune the larger search space.",
            "",
            "1. Anchors: establish the current repo-default, current GTEx no-harmonizome, and current GTEx harmonizome baselines.",
            "2. Focused parameter sweeps: top-k size, score mode, and explicit row-filter sweeps around the baseline models.",
            "3. Workflow design variants: balancing, gene-filter scope, covariate design, and backend validation models.",
            "4. Hybrid library models: cross the most promising DE workflow with the most promising ranking/export behavior from phases 2 and 3.",
            "",
            "## Deliverables Written By This Step",
            "",
            "- `model_manifest.v1.tsv`: one row per proposed model with explicit workflow and extractor settings",
            "- `model_family_summary.v1.tsv`: counts and rationale by family",
            "- `run_summary.v1.tsv`: compact summary of the proposal contents",
            "",
            "## Notes",
            "",
            "- This step proposes models only. It does not run the full GTEx extraction pipeline for each model.",
            "- The proposal assumes GTEx metadata currently available in the repo support at least `sex` and `smtsd` as fixed-effect covariates.",
            "- The highest-value early comparison is between the current GTEx no-harmonizome baseline and the harmonizome-style limma/voom validation model, because that separates extractor choices from backend choices.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(args.log_level, output_dir / "generate_gtex_model_sweep_proposal.v1.log")

    LOGGER.info("building GTEx model sweep proposal")
    model_df = pd.DataFrame(build_model_rows()).sort_values(
        ["category", "execution_priority", "model_family", "model_name"]
    ).reset_index(drop=True)
    LOGGER.info("model manifest shape=%s", model_df.shape)

    family_df = (
        model_df.groupby(["category", "model_family"], as_index=False)
        .agg(
            model_count=("model_name", "size"),
            family_rationale=("rationale", "first"),
        )
        .sort_values(["category", "model_count", "model_family"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    LOGGER.info("family summary shape=%s", family_df.shape)

    run_summary_df = pd.DataFrame(
        [
            {"metric": "analysis_name", "value": "GTEx_model_sweep_v1"},
            {"metric": "anchor_model_count", "value": int((model_df["category"] == "anchor").sum())},
            {"metric": "parameter_sweep_model_count", "value": int((model_df["category"] == "parameter_sweep").sum())},
            {"metric": "defensible_model_count", "value": int((model_df["category"] == "defensible_models").sum())},
            {"metric": "total_model_count", "value": int(model_df.shape[0])},
            {"metric": "model_family_count", "value": int(family_df.shape[0])},
        ]
    )

    write_dataframe(model_df, output_dir / "model_manifest.v1.tsv")
    write_dataframe(family_df, output_dir / "model_family_summary.v1.tsv")
    write_dataframe(run_summary_df, output_dir / "run_summary.v1.tsv")
    write_text(build_markdown(model_df, family_df), output_dir / "gtex_model_sweep_proposal.v1.md")


if __name__ == "__main__":
    main()
