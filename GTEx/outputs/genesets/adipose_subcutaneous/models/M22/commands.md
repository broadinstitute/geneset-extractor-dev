# Commands For M22

## Workflow

```bash
PYTHONPATH=/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src:/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli workflows rna_de_prepare --modality bulk --counts_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/adipose_subcutaneous/prepared/tissue_counts.tsv --matrix_orientation gene_by_sample --feature_id_column gene_id --matrix_gene_symbol_column gene_symbol --sample_metadata_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/adipose_subcutaneous/prepared/sample_metadata.tsv --sample_id_column sample_id --group_column age_bin --comparisons_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/adipose_subcutaneous/prepared/comparisons.tsv --de_mode modern --balance_groups false --balance_seed 0 --gene_filter_scope contrast --backend r_limma_voom --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/adipose_subcutaneous/models/M22/workflow --organism human --genome_build hg38 --covariates SEX
```

## Extractor

```bash
PYTHONPATH=/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src:/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli convert rna_deg_multi --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/adipose_subcutaneous/models/M22/workflow/deg_long.tsv --comparison_column comparison_id --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/adipose_subcutaneous/models/M22/extractor --organism human --genome_build hg38 --signature_name M22 --postprocess_mode legacy --score_mode signed_neglog10padj --select threshold --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol true --emit_small_gene_sets true --disable_default_excludes --padj_max 0.05 --min_score 1.30103 --gmt_source selected --gmt_topk_list 250 --gmt_min_genes 5 --gmt_max_genes 250 --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```
