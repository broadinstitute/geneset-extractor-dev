# Commands For AC4

## Continuous-Age Workflow

```bash
/home/ryank/software/miniconda3/envs/work/bin/Rscript /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC4/workflow/run_continuous_age_limma_voom.R
```

## Tissue DEG Model

The runner fits one limma/voom model across all tissue samples with continuous `age_mid` as the predictor of interest.

The DEG table is written at:
- `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC4/tissue_extractor/tissue_deg.tsv`

Interpretation:
- positive `logFC` / `stat`: expression increases with age
- negative `logFC` / `stat`: expression decreases with age

## Extractor

```bash
cd /home/ryank/software/geneset_extractors/dig-gene-set-extractors
PYTHONPATH=/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli convert rna_deg --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC4/tissue_extractor/tissue_deg.tsv --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC4/tissue_extractor --organism human --genome_build hg38 --signature_name AC4__adipose_subcutaneous --postprocess_mode harmonizome --score_mode auto --select top_k --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol false --emit_small_gene_sets false --gmt_source full --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```
