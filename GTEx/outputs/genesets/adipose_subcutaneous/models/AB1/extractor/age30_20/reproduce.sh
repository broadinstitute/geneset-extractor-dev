#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$PWD/replay}"
mkdir -p "$ROOT"
cd "$ROOT"

echo "Running prepare_deg_long"
/home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli workflows rna_de_prepare --comparisons_tsv comparisons.tsv --counts_tsv tissue_counts.tsv --sample_metadata_tsv sample_metadata.tsv --approximate_repeated_measures false --backend r_limma_voom --balance_groups false --balance_seed 0 --covariates SEX --de_mode modern --gene_filter_scope contrast --genome_build hg38 --modality bulk --organism human --repeated_measures false

echo "Running generate_4bc2f5ff27aaa09896969532"
/home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli --deg_tsv deg_long.tsv --gtf gencode.v26.annotation.gtf.gz --columns '{"gene_id_column": "gene_id", "gene_symbol_column": "gene_symbol", "logfc_column": "logFC", "padj_column": "padj", "pvalue_column": "pvalue", "score_column": null, "stat_column": "stat"}' --comparison_label age30_20 --disable_default_excludes true --duplicate_gene_policy max_abs --emit_full true --emit_gmt true --emit_small_gene_sets true --gmt_emit_abs false --gmt_max_genes 250 --gmt_min_genes 5 --gmt_prefer_symbol true --gmt_require_symbol true --gmt_source selected --gmt_split_signed true --gmt_topk_list 250 --min_score 1.30103 --neglog10p_cap 50.0 --neglog10p_eps 1e-300 --normalize within_set_l1 --padj_max 0.05 --quantile 0.01 --score_mode signed_neglog10padj --score_mode_requested signed_neglog10padj --selection_method threshold --signature_name AB1 --top_k 200

