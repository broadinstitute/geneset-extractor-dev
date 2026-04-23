# legacy_signedfdr005_logfc050 v1

## Model Identity

- model_name: `legacy_signedfdr005_logfc050`
- category: `parameter_sweep`
- model_family: `legacy_filter_sweep`
- execution_priority: `12`

## Design Intent

Legacy-style extraction with explicit significance/effect-size row filters.

## Workflow Settings

- workflow_name: `de=modern__balance=false__seed=0__scope=contrast__covariates=sex,smtsd__backend=lightweight`
- workflow_source: `reuse_existing_gtex_noharm`
- workflow_de_mode: `modern`
- workflow_balance_groups: `false`
- workflow_balance_seed: `0`
- workflow_gene_filter_scope: `contrast`
- workflow_covariates: `sex,smtsd`
- workflow_backend: `lightweight`
- workflow_deg_long_tsv: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_no_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`

## Extractor Settings

- extractor_postprocess_mode: `legacy`
- extractor_score_mode: `signed_neglog10padj`
- extractor_select: `top_k`
- extractor_top_k: `200`
- extractor_padj_max: `0.05`
- extractor_pvalue_max: ``
- extractor_min_abs_logfc: `0.50`
- extractor_gmt_source: `full`
- extractor_gmt_topk_list: `200`
- extractor_gmt_min_genes: `100`
- extractor_gmt_max_genes: `500`
- extractor_disable_default_excludes: `false`
- extractor_gmt_biotype_allowlist: `protein_coding`

## Commands To Run This Model

Workflow step:

```bash
bash run/gtex_model_sweep_v1/run_workflow_de_modern__balance_false__seed_0__scope_contrast__covariates_sex_smtsd__backend_lightweight.v1.sh
```

Model extraction step:

```bash
bash run/gtex_model_sweep_v1/run_model_legacy_signedfdr005_logfc050.v1.sh
```

## Expected Outputs

- named_model_gmt_gz: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/models/legacy_signedfdr005_logfc050/legacy_signedfdr005_logfc050.v1.gmt.gz`
- comparison_to_reference_tsv: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/models/legacy_signedfdr005_logfc050/comparison_to_reference.v1.tsv`
- comparison_to_reference_md: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/models/legacy_signedfdr005_logfc050/comparison_to_reference.v1.md`

## Rationale

Tests significance plus stronger effect-size gating.
