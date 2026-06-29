# genesets.gmt Command Provenance

- generated_at: `2026-05-05T14:09:09+00:00`
- output_gmt: `/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AB14/extractor/age50_20/genesets.gmt`
- tissue_id: `adipose_subcutaneous`
- model_group: `age_binned`
- model_id: `AB14`
- scope: `comparison`
- scope_label: `age50_20`

## Top-Level Wrapper Command

```bash
bash /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/run/run_age_binned_model.sh --model_id AB14 --prepared_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared --run_root /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models --python_bin /home/ryank/software/miniconda3/envs/work/bin/python --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

## Recorded Model Commands

These commands were recorded with the model output and correspond to the workflow and extractor stages.

# Commands For AB14

## Workflow

```bash
PYTHONPATH=/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli workflows rna_de_prepare --modality bulk --counts_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/tissue_counts.tsv --matrix_orientation gene_by_sample --feature_id_column gene_id --matrix_gene_symbol_column gene_symbol --sample_metadata_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/sample_metadata.tsv --sample_id_column sample_id --group_column age_bin --comparisons_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/prepared/comparisons.tsv --de_mode modern --balance_groups false --balance_seed 0 --gene_filter_scope contrast --backend lightweight --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AB14/workflow --organism human --genome_build hg38 --covariates SEX
```

## Extractor

```bash
PYTHONPATH=/home/ryank/software/geneset_extractors/dig-gene-set-extractors/src /home/ryank/software/miniconda3/envs/work/bin/python -m geneset_extractors.cli convert rna_deg_multi --deg_tsv /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AB14/workflow/deg_long.tsv --comparison_column comparison_id --out_dir /home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/outputs/genesets/adipose_subcutaneous/models/AB14/extractor --organism human --genome_build hg38 --signature_name AB14 --postprocess_mode legacy --score_mode signed_neglog10padj --select threshold --normalize within_set_l1 --emit_full true --emit_gmt true --gmt_split_signed true --gmt_require_symbol true --emit_small_gene_sets true --disable_default_excludes --padj_max 0.05 --min_score 1.30103 --gmt_source selected --gmt_topk_list 250 --gmt_min_genes 5 --gmt_max_genes 250 --gtf /home/ryank/software/geneset_extractors/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz
```

## Logged Executed Commands

No explicit `$ ...` command lines were recorded in `run.log` for this model output.

## Notes

- For tissue models, one continuous-age R workflow run produces `tissue_deg.tsv`, then one `rna_deg` extractor run produces the tissue-level `genesets.gmt`.
