# AB6 Provenance

## Intent

- Model: `AB6`
- Rationale: tests direct statistic ranking

## Full Pipeline Commands

### 1. Prepare tissue inputs

```bash
bash geneset-extractor-dev/GTEx/run/build_tissue_inputs.sh \
  --counts_gct <path_to_gtex_tissue_counts.gct.gz> \
  --sample_metadata_tsv <path_to_sample_attributes.tsv> \
  --subject_metadata_tsv <path_to_subject_phenotypes.tsv> \
  --tissue_label <human_readable_tissue_label> \
  --out_dir <prepared_dir>
```

### 2. Run this model

```bash
bash geneset-extractor-dev/GTEx/run/run_age_binned_model.sh \
  --model_id AB6 \
  --prepared_dir <prepared_dir> \
  --run_root <model_run_root>
```

## Underlying Workflow Settings

- `de_mode=harmonizome`
- `backend=lightweight`
- `balance_groups=true`
- `balance_seed=1`
- `gene_filter_scope=stratum`
- `covariates=SEX`

## Underlying Extractor Settings

- `postprocess_mode=legacy`
- `score_mode=stat`
- `padj_max=0.05`
- `pvalue_max=NA`
- `min_abs_logfc=NA`
- `disable_default_excludes=true`
- `select=top_k`
- `top_k=250`
- `min_score=NA`
- `gmt_source=selected`
- `gmt_topk_list=250`
- `gmt_min_genes=5`
- `gmt_max_genes=250`
- `gmt_biotype_allowlist=`
- `gmt_require_symbol=true`
- `emit_small_gene_sets=true`
