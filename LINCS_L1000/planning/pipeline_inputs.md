# LINCS_L1000 Pipeline Inputs

The current LINCS L1000 pipeline supports two all-signatures `HZ*` models:

- `HZ1`
  - chemical perturbation consensus signatures
- `HZ2`
  - CRISPR knockout consensus signatures

## Planning inputs

- `config/model_list.tsv`
- `config/model_manifest.tsv`

## Biological and mapping inputs

For `HZ1`:

- `inputs/LINCS_L1000/cp_mean_coeff_mat.tsv.gz`

For `HZ2`:

- `inputs/LINCS_L1000/xpr_mean_coeff_mat.tsv.gz`

Shared:

- `HarmonizomePythonScripts/mappingFile_2017.txt`

## Software inputs

- `dig-gene-set-extractors/`

## Runtime shape

`HZ1` runs through:

- `geneset_extractors.cli workflows lincs_l1000_chempert`
- `geneset_extractors.cli convert signed_term_gene`

`HZ2` runs through:

- `geneset_extractors.cli workflows lincs_l1000_crisprko`
- `geneset_extractors.cli convert signed_term_gene`

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./lincs_l1000_outputs/`

The all-signatures output tree is:

- `lincs_l1000_outputs/genesets/all_signatures/models/HZ1/`
- `lincs_l1000_outputs/genesets/all_signatures/models/HZ2/`

The authoritative GMT output for each model is:

- `extractor/genesets.gmt`

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
