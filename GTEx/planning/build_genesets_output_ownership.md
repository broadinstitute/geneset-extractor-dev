# `build_genesets.sh` Output Ownership

This note covers only the `build_genesets.sh` pipeline stage.

## Created By `geneset-extractor-dev`

### Prepared tissue bundle

Under:

- `gtex_outputs/genesets/<tissue>/prepared/`

Files:

- `tissue_counts.tsv`
- `sample_metadata.tsv`
- `comparisons.tsv`
- `prepare_summary.json`
- `naming_reference.md`

### Per-model GTEx-local orchestration files

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/`

Files:

- `commands.md`
- `run.log`

### Additional GTEx-local files for `AC*` models

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/workflow/`
- `gtex_outputs/genesets/<tissue>/models/<model_id>/tissue_extractor/`

Files:

- `workflow/continuous_sample_metadata.tsv`
- `workflow/continuous_sample_metadata.md`
- `workflow/continuous_sample_metadata.log`
- `workflow/run_continuous_age_limma_voom.R`
- `tissue_extractor/tissue_deg.tsv`
- `tissue_extractor/tissue_deg.md`
- `tissue_extractor/tissue_deg.log`
- `tissue_extractor/naming_reference.md`

## Created By `dig-gene-set-extractors`

### `AB*` model workflow outputs

Under:

- `gtex_outputs/genesets/<tissue>/models/<model_id>/workflow/`

Important files:

- `deg_long.tsv`
- `deg_long.provenance_graph.json`
- `prepare_summary.json`
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

## Files Required To Run `build_genesets.sh`

### External inputs

- sample metadata TSV
- subject metadata TSV
- `dig-gene-set-extractors` checkout
- counts GCT path or paths referenced by `tissue_list.tsv`
- `--gtf` when required by the active `model_list.tsv`
- `Rscript` only when selected models include `AC*`

### Planning and configuration inputs

- `model_list.tsv`
- `tissue_list.tsv`
- age-binned model manifest
- continuous-age model manifest

## Internal Build Dependencies

### Shared prepared bundle

The prepared bundle must exist before any model runs:

- `prepared/tissue_counts.tsv`
- `prepared/sample_metadata.tsv`

### `AB*` model requirements

`AB*` runs require:

- `prepared/tissue_counts.tsv`
- `prepared/sample_metadata.tsv`
- `prepared/comparisons.tsv`

### `AC*` model requirements

`AC*` runs require:

- `prepared/tissue_counts.tsv`
- `prepared/sample_metadata.tsv`

## Summary

The clean ownership split for `build_genesets.sh` is:

- `geneset-extractor-dev` creates the prepared tissue bundle and the GTEx-local orchestration and logging files.
- `dig-gene-set-extractors` creates the differential expression workflow outputs and extractor outputs from that prepared bundle.
