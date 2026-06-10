# HuBMAP Pipeline Inputs

The current HuBMAP pipeline supports two all-signatures `HZ*` models:

- `HZ1`
  - base ASCT+B
- `HZ2`
  - augmented ASCT+B

## Planning inputs

- `planning/model_list.tsv`
- `planning/model_manifest.tsv`

## Biological and mapping inputs

For `HZ1`:

- `inputs/HuBMAP/ASCT+B/v2.2`
- `inputs/human_gene_info`

For `HZ2`:

- base matrix such as:
  - `outputs_hubmap/gene_attribute_matrix.txt.gz`
- `inputs/human_gene_info`

If `HZ1` has already been run in the same output root, `HZ2` can also reuse:

- `genesets/all_signatures/models/HZ1/workflow/gene_attribute_matrix.txt.gz`

## Software inputs

- `dig-gene-set-extractors/`

## Output behavior

If `--out_root` is omitted, outputs go under:

- `./hubmap_outputs/`

The all-signatures output tree is:

- `hubmap_outputs/genesets/all_signatures/models/HZ1/`
- `hubmap_outputs/genesets/all_signatures/models/HZ2/`

The authoritative GMT output for each model is:

- `extractor/genesets.gmt`

The runtime shape is now:

- `HZ1`
  - `dig workflows hubmap_asctb`
  - `dig convert unsigned_term_gene`
- `HZ2`
  - `dig workflows hubmap_asctb_augmented`
  - `dig convert unsigned_term_gene`

`geneset-extractor-dev/HuBMAP` is now primarily responsible for:

- model selection
- argument resolution
- commands/log packaging

The functional workflow logic lives in `dig-gene-set-extractors`.

Optional provenance mirror inputs supported by the build entrypoint:

- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`
