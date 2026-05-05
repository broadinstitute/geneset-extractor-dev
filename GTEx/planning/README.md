# GTEx Planning

This directory is organized around the current GTEx workflow rather than the historical step-by-step buildout.

## Current Flow

1. Build GTEx tissue inputs
2. Build tissue-by-model gene sets and GMT files
3. Optionally evaluate those gene sets with PIGEAN and EAGGL
4. Summarize model behavior and choose representative models

## Current Entry Points

- `geneset-extractor-dev/GTEx/run/build_genesets.sh`
- `geneset-extractor-dev/GTEx/run/run_pigean.sh`
- `geneset-extractor-dev/GTEx/run/run_eaggl.sh`
- `geneset-extractor-dev/GTEx/run/summarize_model_enrichment.sh`
- `geneset-extractor-dev/GTEx/run/summarize_top_models.sh`

## Planning Layout

- `geneset_build/`
  - planning for generating GTEx gene sets and GMT outputs
- `model_evaluation/`
  - planning for optional downstream model evaluation
- `shared/`
  - naming and cross-cutting conventions

## Build First

The primary analysis products are the gene-set outputs under:

- `geneset-extractor-dev/GTEx/outputs/genesets/<tissue>/models/`

This is the first phase the user runs:

- `geneset-extractor-dev/GTEx/run/build_genesets.sh`

Selection inputs for models and tissues are maintained directly under planning:

- `geneset-extractor-dev/GTEx/planning/model_list.tsv`
- `geneset-extractor-dev/GTEx/planning/tissue_list.tsv`
- `geneset-extractor-dev/GTEx/planning/selection_inputs.md`

Age-binned wrapper notes and per-model provenance are folded into:

- `geneset-extractor-dev/GTEx/planning/geneset_build/age_binned_models/`

There is intentionally no separate runtime-interface planning bundle for continuous-age models.

## Optional Evaluation

PIGEAN and EAGGL are downstream and optional. They consume previously generated GMT outputs and write evaluation outputs under:

- `geneset-extractor-dev/GTEx/outputs/pigean_eaggl/`

Relevant wrappers:

- `geneset-extractor-dev/GTEx/run/run_pigean.sh`
- `geneset-extractor-dev/GTEx/run/run_eaggl.sh`
- `geneset-extractor-dev/GTEx/run/summarize_model_enrichment.sh`
- `geneset-extractor-dev/GTEx/run/summarize_top_models.sh`

## Model Families

- `AB*`: age-binned contrast models
- `AC*`: continuous-age models
- `TV*`: reserved for future tissue-versus-reference models
