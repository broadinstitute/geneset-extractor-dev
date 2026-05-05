# AB2 Provenance

## Intent

- Model: `AB2`
- Rationale: conservative balanced GTEx baseline using both harmonizome presets

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
  --model_id AB2 \
  --prepared_dir <prepared_dir> \
  --run_root <model_run_root>
```

## Underlying Workflow Settings

- `de_mode=harmonizome`
- `backend=auto`
- `balance_groups=true`
- `balance_seed=1`
- `gene_filter_scope=stratum`
- `covariates=SEX`

## Underlying Extractor Settings

- `postprocess_mode=harmonizome`
- `score_mode=auto`
- `padj_max=NA`
- `pvalue_max=NA`
- `min_abs_logfc=NA`
- `disable_default_excludes=false`
- `select=top_k`
- `top_k=NA`
- `min_score=NA`
- `gmt_source=full`
- `gmt_topk_list=NA`
- `gmt_min_genes=NA`
- `gmt_max_genes=NA`
- `gmt_biotype_allowlist=protein_coding`
- `gmt_require_symbol=true`
- `emit_small_gene_sets=false`
