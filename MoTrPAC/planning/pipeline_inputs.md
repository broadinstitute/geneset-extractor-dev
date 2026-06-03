# MoTrPAC Pipeline Inputs

The current MoTrPAC pipeline supports:

- tissue-scoped raw-count models:
  - `TR1`
  - `TW1`
- all-tissues released-DEA model:
  - `HZ1`

## Planning inputs

- `planning/tissue_list.tsv`
- `planning/model_list.tsv`
- `planning/model_manifest.tsv`

## Biological and mapping inputs for `TR1` and `TW1`

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

## Released-DEA inputs for `HZ1`

- feature annotation:
  - `inputs/MoTrPAC/MotrpacRatTraining6moData/transcriptomics/analysis/transcript-rna-seq/feature-annot/TRNSCRPT_FEATURE_ANNOT.txt`
- released DEA directory:
  - `inputs/MoTrPAC/MotrpacRatTraining6moData/transcriptomics/analysis/transcript-rna-seq/dea/`
- Harmonizome mapping file:
  - `HarmonizomePythonScripts/mappingFile_2017.txt`

Optional `HZ1` extras:

- `--gene_info`
- `--gene_csv`

## Software inputs

- `dig-gene-set-extractors/`
- `Rscript`
- R packages:
  - `edgeR`
  - `limma`

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./motrpac_outputs/`

The main output tree for tissue-scoped models is:

- `motrpac_outputs/genesets/<tissue>/`

The `HZ1` all-tissues model writes under:

- `motrpac_outputs/genesets/all_tissues/models/HZ1/`

Its authoritative GMT output is:

- `motrpac_outputs/genesets/all_tissues/models/HZ1/tissue_extractor/genesets.gmt`

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
