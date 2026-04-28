# Commands For T9

## Continuous-Age Workflow

```bash
/home/ryank/software/miniconda3/envs/work/bin/Rscript /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/tissue_models/T9/workflow/run_continuous_age_limma_voom.R
```

## Tissue DEG Model

The runner fits one limma/voom model across all tissue samples with continuous `age_mid` as the predictor of interest.

The DEG table is written at:
- `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/tissue_models/T9/tissue_extractor/tissue_deg.tsv`

Interpretation:
- positive `logFC` / `stat`: expression increases with age
- negative `logFC` / `stat`: expression decreases with age

## Extractor

```bash
cd /home/ryank/software/geneset_extractors/dig-gene-set-extractors
PYTHONPATH=/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src:/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli convert rna_deg --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/tissue_models/T9/tissue_extractor/tissue_deg.tsv --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/tissue_models/T9/tissue_extractor --organism human --genome_build hg38 --signature_name T9__adipose_subcutaneous --postprocess_mode legacy --score_mode logfc_times_neglog10p --select top_k --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol true --emit_small_gene_sets true --disable_default_excludes --padj_max 0.05 --top_k 250 --gmt_source selected --gmt_topk_list 250 --gmt_min_genes 5 --gmt_max_genes 250 --gmt_biotype_allowlist protein_coding
```
