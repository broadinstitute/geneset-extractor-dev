# run_gtex_parameter_sweep.v1

This script runs a focused `rna_deg_multi` parameter sweep against the existing combined DEG table from `gtex_no_harmonizome_analysis_v1` and scores each output against the legacy GTEx aging GMT.

Inputs:

- `outputs/gtex_no_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`
- `GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz`
- local `dig-gene-set-extractors` checkout

What it does:

1. builds a fixed grid of `rna_deg_multi` configurations
2. runs each configuration in its own output subdirectory
3. converts the generated GMT names back to legacy GTEx set names
4. compares each run to the legacy GMT by shared set names and per-set Jaccard overlap
5. writes run-level summary tables and a markdown findings report

Main outputs:

- `outputs/gtex_parameter_sweep_v1/parameter_sweep_summary.v1.tsv`
- `outputs/gtex_parameter_sweep_v1/parameter_effects.v1.tsv`
- `outputs/gtex_parameter_sweep_v1/findings.v1.md`

The sweep is centered on parameters that can directly change GMT membership:

- `postprocess_mode`
- `gmt_source`
- `score_mode`
- `gmt_topk_list`
- `padj_max`
- `min_abs_logfc`

For `gmt_source=selected` it also varies `select` and `top_k`, because those only affect GMT membership in that mode.
