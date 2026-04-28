# genesets.gmt Command Provenance

- generated_at: `2026-04-28T15:41:42+00:00`
- output_gmt: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/M14/extractor/age50_20/genesets.gmt`
- tissue_id: `adipose_subcutaneous`
- model_group: `models`
- model_id: `M14`
- scope: `comparison`
- scope_label: `age50_20`

## Top-Level Wrapper Command

```bash
bash /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/run/run_gtex_model.sh --model_id M14 --prepared_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared --run_root /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models --python_bin /home/ryank/software/miniconda3/envs/work/bin/python --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

## Recorded Model Commands

These commands were recorded with the model output and correspond to the workflow and extractor stages.

# Commands For M14

## Workflow

```bash
PYTHONPATH=/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src:/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src python3 -m geneset_extractors.cli workflows rna_de_prepare --modality bulk --counts_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/tissue_counts.tsv --matrix_orientation gene_by_sample --feature_id_column gene_id --matrix_gene_symbol_column gene_symbol --sample_metadata_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/sample_metadata.tsv --sample_id_column sample_id --group_column age_bin --comparisons_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/comparisons.tsv --de_mode modern --balance_groups false --balance_seed 0 --gene_filter_scope contrast --backend lightweight --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/M14/workflow --organism human --genome_build hg38 --covariates SEX
```

## Extractor

```bash
PYTHONPATH=/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src:/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src python3 -m geneset_extractors.cli convert rna_deg_multi --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/M14/workflow/deg_long.tsv --comparison_column comparison_id --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/M14/extractor --organism human --genome_build hg38 --signature_name M14 --postprocess_mode legacy --score_mode signed_neglog10padj --select threshold --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol true --emit_small_gene_sets true --disable_default_excludes --padj_max 0.05 --min_score 1.30103 --gmt_source selected --gmt_topk_list 250 --gmt_min_genes 5 --gmt_max_genes 250 --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

## Logged Executed Commands

No explicit `$ ...` command lines were recorded in `run.log` for this model output.

## Notes

- For comparison models, one workflow run produces `workflow/deg_long.tsv` and one extractor run produces both the combined root `genesets.gmt` and the per-comparison `age*/genesets.gmt` files.
- The same wrapper, workflow, and extractor commands apply to each `age*/genesets.gmt` file under the model.
