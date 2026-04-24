# harm_signedfdr250_pcoding v1

## Model Identity

- model_name: `harm_signedfdr250_pcoding`
- category: `defensible_models`
- model_family: `annotation_filters`
- execution_priority: `26`

## Design Intent

Keep harmonizome-style DE and ranking but restore a protein-coding bias in the emitted GMT.

## Workflow Settings

- workflow_name: `de=harmonizome__balance=true__seed=1__scope=stratum__covariates=sex,smtsd__backend=lightweight`
- workflow_source: `reuse_existing_gtex_harm`
- workflow_de_mode: `harmonizome`
- workflow_balance_groups: `true`
- workflow_balance_seed: `1`
- workflow_gene_filter_scope: `stratum`
- workflow_covariates: `sex,smtsd`
- workflow_backend: `lightweight`
- workflow_deg_long_tsv: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`

## Extractor Settings

- extractor_postprocess_mode: `harmonizome`
- extractor_score_mode: `signed_neglog10padj`
- extractor_select: `threshold`
- extractor_top_k: `250`
- extractor_padj_max: `0.05`
- extractor_pvalue_max: ``
- extractor_min_abs_logfc: ``
- extractor_gmt_source: `selected`
- extractor_gmt_topk_list: `250`
- extractor_gmt_min_genes: `5`
- extractor_gmt_max_genes: `500`
- extractor_disable_default_excludes: `true`
- extractor_gmt_biotype_allowlist: `protein_coding`

## Commands To Run This Model

Workflow step:

```bash
bash run/gtex_model_sweep_v1/run_workflow_de_harmonizome__balance_true__seed_1__scope_stratum__covariates_sex_smtsd__backend_lightweight.v1.sh
```

Model extraction step:

```bash
bash run/gtex_model_sweep_v1/run_model_harm_signedfdr250_pcoding.v1.sh
```

## Expected Outputs

- named_model_gmt_gz: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/models/harm_signedfdr250_pcoding/harm_signedfdr250_pcoding.v1.gmt.gz`
- comparison_to_reference_tsv: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/models/harm_signedfdr250_pcoding/comparison_to_reference.v1.tsv`
- comparison_to_reference_md: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/gtex_model_sweep_v1/models/harm_signedfdr250_pcoding/comparison_to_reference.v1.md`

## Rationale

Tests whether legacy mismatch is driven partly by harmonizome-mode inclusion of non-protein-coding genes.
