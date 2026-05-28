# MoTrPAC Pipeline Inputs

The current minimal MoTrPAC pipeline expects:

## Planning inputs

- `planning/tissue_list.tsv`
- `planning/model_list.tsv`
- `planning/model_manifest.tsv`

## Biological and mapping inputs

- one tissue raw-count matrix, for example:
  - `inputs/MoTrPAC/motrpac_test/raw_counts_by_tissue/TRNSCRPT_LIVER_RAW_COUNTS.tsv.gz`
- transcript metadata:
  - `inputs/MoTrPAC/motrpac_test/TRNSCRPT_META_sample_metadata.tsv.gz`
- phenotype metadata:
  - `inputs/MoTrPAC/motrpac_test/PHENO_sample_metadata.tsv.gz`
- feature-to-gene mapping:
  - `inputs/MoTrPAC/motrpac_test/FEATURE_TO_GENE_transcriptomics_subset.tsv.gz`
- rat-to-human ortholog mapping:
  - `inputs/MoTrPAC/motrpac_test/RAT_TO_HUMAN_GENE.tsv.gz`

## Software inputs

- `dig-gene-set-extractors/`
- `Rscript`
- R packages:
  - `edgeR`
  - `limma`

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./motrpac_outputs/`

The main output tree is:

- `motrpac_outputs/genesets/<tissue>/`

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
