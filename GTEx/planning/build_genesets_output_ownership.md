# `build_genesets.sh` Output Ownership

This note covers only the `build_genesets.sh` pipeline stage.

## Created By `geneset-extractor-dev`

### Per-model GTEx-local orchestration files

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/`

Files:

- `commands.md`
- `run.log`

### Additional GTEx-local files for `AC*` models

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/tissue_extractor/`

Files:

- `tissue_extractor/naming_reference.md`

## Created By `dig-gene-set-extractors`

### `AB*` model workflow outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/workflow/`

Important files:

- `deg_long.tsv`
- `deg_long.provenance_graph.json`
- `tissue_counts.tsv`
- `sample_metadata.tsv`
- `comparisons.tsv`
- `comparison_manifest.tsv`
- `comparison_audit.tsv`
- `comparison_selected_samples.tsv`

Also under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/workflow/backend_work/`

Examples:

- `comparisons.tsv`
- `metadata.tsv`
- `counts_gene_by_sample.tsv`
- `deg_long.tsv`
- `comparison_selected_samples.tsv`
- `run_limma_voom.R`

### `AB*` model extractor outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/extractor/`

Top-level files:

- `manifest.tsv`
- `genesets.gmt`

Per-comparison files under directories such as `age30_20/`, `age40_20/`, `age50_20/`, `age60_20/`, `age70_20/`:

- `geneset.tsv`
- `geneset.full.tsv`
- `geneset.meta.json`
- `geneset.provenance.json`
- `genesets.gmt`
- `run_summary.json`
- `run_summary.txt`

### `AC*` model workflow outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/workflow/`

Important files:

- `deg_long.tsv`
- `deg_long.provenance_graph.json`
- `tissue_counts.tsv`
- `sample_metadata.tsv`
- `continuous_sample_metadata.tsv`
- `run_continuous_age_limma_voom.R`

### `AC*` model extractor outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/tissue_extractor/`

Important files:

- `genesets.gmt`
- `geneset.tsv`
- `geneset.full.tsv`
- `geneset.meta.json`
- `geneset.provenance.json`
- `run_summary.json`
- `run_summary.txt`

### `HZ*` notebook-style workflow outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/workflow/`

Important files:

- `sample_metadata.tsv`
- `counts_gene_by_sample.tsv`
- `comparison_manifest.tsv`
- `comparison_audit.tsv`
- `comparison_selected_samples.tsv`
- `comparisons/<comparison_id>.tsv`
- `deg_long.tsv`
- `deg_long.provenance_graph.json`
- `prepare_summary.json`

### `HZ*` notebook-style extractor outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/extractor/`

Top-level files:

- `manifest.tsv`
- `genesets.gmt`

Per-comparison files under directories such as `age30_20/`, `age40_20/`, `age50_20/`, `age60_20/`, `age70_20/`:

- `geneset.tsv`
- `geneset.full.tsv`
- `geneset.meta.json`
- `geneset.provenance.json`
- `genesets.gmt`
- `run_summary.json`
- `run_summary.txt`

## Files Required To Run `build_genesets.sh`

### External inputs

- sample metadata TSV
- subject metadata TSV
- counts GCT supplied explicitly via `--counts_gct`
- `human_gene_info` when selected models include `HZ*`
- `dig-gene-set-extractors` checkout
- `--gtf` when required by the active `model_list.tsv`
- `Rscript` only when selected models include `AC*`

### Planning and configuration inputs

- `model_list.tsv`
- `tissue_list.tsv`
- age-binned model manifest
- continuous-age model manifest

## Internal Build Dependencies

### `AB*` model requirements

`AB*` runs now require:

- raw counts GCT from the active tissue or broad tissue list
- sample attributes TSV
- subject phenotypes TSV
- `dig-gene-set-extractors`

### `AC*` model requirements

`AC*` runs now require:

- raw counts GCT from the active tissue or broad tissue list
- sample attributes TSV
- subject phenotypes TSV
- `dig-gene-set-extractors`
- `Rscript`

### `HZ*` model requirements

`HZ*` runs use the GTEx outer model tree but do not depend on the standard prepared tissue bundle semantics.

They require:

- a broad-tissue `counts_gct` entry from the active broad tissue list
- sample attributes TSV
- subject phenotypes TSV
- `human_gene_info`
- `dig-gene-set-extractors`

## Summary

The clean ownership split for `build_genesets.sh` is:

- `geneset-extractor-dev` creates the GTEx-local orchestration and logging files.
- `dig-gene-set-extractors` creates the differential expression workflow outputs and extractor outputs for `AB*`, `AC*`, and `HZ*`.
