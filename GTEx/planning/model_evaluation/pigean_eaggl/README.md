# PIGEAN And EAGGL Evaluation

This planning area covers the optional downstream evaluation layer for GTEx model outputs.

## Inputs

The evaluation step assumes that geneset generation has already completed and that GMT files exist under:

- `geneset-extractor-dev/GTEx/outputs/genesets/<tissue>/models/`

## Purpose

PIGEAN and EAGGL are used to compare model outputs and help determine which models capture tissue-relevant biology most consistently.

## Run Order

1. Run geneset generation first
2. Optionally run:
   - `geneset-extractor-dev/GTEx/run/run_pigean.sh`
   - `geneset-extractor-dev/GTEx/run/run_eaggl.sh`
3. Optionally summarize:
   - `geneset-extractor-dev/GTEx/run/summarize_model_enrichment.sh`
   - `geneset-extractor-dev/GTEx/run/summarize_top_models.sh`

## Outputs

Evaluation outputs are written under:

- `geneset-extractor-dev/GTEx/outputs/pigean_eaggl/`

This includes per-query raw outputs, biology summaries, and model-ranking summaries.
