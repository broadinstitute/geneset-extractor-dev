# genesets.gmt Command Provenance

- generated_at: `2026-05-05T14:09:09+00:00`
- output_gmt: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/tissue_extractor/genesets.gmt`
- tissue_id: `adipose_subcutaneous`
- model_group: `continuous_age`
- model_id: `AC2`
- scope: `tissue`
- scope_label: `adipose_subcutaneous`

## Top-Level Wrapper Command

```bash
bash /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/run/run_gtex_tissue_gmt.sh --python_bin /home/ryank/software/miniconda3/envs/work/bin/python --rscript_bin /home/ryank/software/miniconda3/envs/work/bin/Rscript --tissue_id adipose_subcutaneous --prepared_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared --run_root /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models --model_ids AC2 --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

## Workflow Script Path

- `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/workflow/run_continuous_age_limma_voom.R`

## Recorded Model Commands

These commands were recorded with the model output and correspond to the workflow and extractor stages.

# Commands For AC2

## Continuous-Age Workflow

```bash
/home/ryank/software/miniconda3/envs/work/bin/Rscript /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/workflow/run_continuous_age_limma_voom.R
```

## Tissue DEG Model

The runner fits one limma/voom model across all tissue samples with continuous `age_mid` as the predictor of interest.

The DEG table is written at:
- `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/tissue_extractor/tissue_deg.tsv`

Interpretation:
- positive `logFC` / `stat`: expression increases with age
- negative `logFC` / `stat`: expression decreases with age

## Extractor

```bash
cd /home/ryank/software/geneset_extractors/dig-gene-set-extractors
PYTHONPATH=/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli convert rna_deg --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/tissue_extractor/tissue_deg.tsv --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/tissue_extractor --organism human --genome_build hg38 --signature_name AC2__adipose_subcutaneous --postprocess_mode harmonizome --score_mode auto --select top_k --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol true --emit_small_gene_sets false --gmt_source full --gmt_biotype_allowlist protein_coding
```

## Logged Executed Commands

```bash
/home/ryank/software/miniconda3/envs/work/bin/Rscript /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/workflow/run_continuous_age_limma_voom.R
```

```bash
/home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli convert rna_deg --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/tissue_extractor/tissue_deg.tsv --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AC2/tissue_extractor --organism human --genome_build hg38 --signature_name AC2__adipose_subcutaneous --postprocess_mode harmonizome --score_mode auto --select top_k --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol true --emit_small_gene_sets false --gmt_source full --gmt_biotype_allowlist protein_coding
```

## Notes

- For tissue models, one continuous-age R workflow run produces `tissue_deg.tsv`, then one `rna_deg` extractor run produces the tissue-level `genesets.gmt`.
