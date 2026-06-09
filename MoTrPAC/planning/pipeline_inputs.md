# MoTrPAC Pipeline Inputs

The current MoTrPAC pipeline supports:

- tissue-scoped raw-count models:
  - `TR1`
  - `TR2`
  - `TW1`
  - `TW2`
- all-tissues aggregated models:
  - `HZ1`
  - `HZ2`
  - `HZ3`

## Planning inputs

- `config/tissue_list.tsv`
- `config/model_list.tsv`
- `config/model_manifest.tsv`

## Biological and mapping inputs for `TR*`, `TW*`, and raw aggregated `HZ*`

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

`TR1` and `TR2` both start from the prepared tissue bundle and run through a `dig` workflow:

- pooled contrast:
  - `training` vs `control`
- model variants:
  - `TR1`: pooled with sex covariate
  - `TR2`: pooled without sex covariate
- workflow:
  - `geneset_extractors.cli workflows motrpac_training`
- extractor:
  - `geneset_extractors.cli convert rna_deg`

`TW1` and `TW2` start from the prepared tissue bundle with stratified contrasts:

- `TW1`:
  - `training` vs `control` within each `tissue × sex × timepoint` stratum
  - workflow:
    - `geneset_extractors.cli workflows motrpac_timewise`
- `TW2`:
  - `training` vs `control` within each `tissue × timepoint` stratum
  - sex pooled into the stratum and included as a covariate
  - workflow:
    - `geneset_extractors.cli workflows motrpac_timepoint`
- extractor:
  - `geneset_extractors.cli convert rna_deg_multi`

`HZ2` and `HZ3` are all-tissues aggregated models built from raw-count-derived contrasts:

- `HZ2`:
  - aggregates pooled raw contrasts across tissues
  - source contrast style: `TR1`
- `HZ3`:
  - aggregates stratified raw contrasts across tissues
  - source contrast style: `TW1`
- workflow:
  - `geneset_extractors.cli workflows motrpac_raw_aggregated`
- extractor:
  - `geneset_extractors.cli convert signed_term_gene`

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

`HZ1` runs through a `dig` workflow from the released DEA inputs:

- workflow:
  - `geneset_extractors.cli workflows motrpac_released_dea`
- extractor:
  - `geneset_extractors.cli convert signed_term_gene`

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

The all-tissues `HZ*` models write under:

- `motrpac_outputs/genesets/all_tissues/models/HZ1/`
- `motrpac_outputs/genesets/all_tissues/models/HZ2/`
- `motrpac_outputs/genesets/all_tissues/models/HZ3/`

Their authoritative GMT output is:

- `motrpac_outputs/genesets/all_tissues/models/HZ*/extractor/genesets.gmt`

Their workflow-side signed term-gene table is:

- `motrpac_outputs/genesets/all_tissues/models/HZ*/workflow/motrpac_signed_term_gene.tsv`

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
