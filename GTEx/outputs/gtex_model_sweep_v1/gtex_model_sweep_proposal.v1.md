# GTEx Model Sweep Proposal v1

## Objective

This proposal defines step 1 of `GTEx_model_sweep_v1`: a concrete, versioned model catalog for generating multiple GTEx aging-signature GMT libraries from `dig-gene-set-extractors`.
The proposal is grounded in the current extractor CLI and RNA-seq guidance, and separates three concerns that can change final gene inclusion:

- upstream DE fitting choices in `workflows rna_de_prepare`
- downstream row filtering, ranking, and GMT emission choices in `convert rna_deg_multi`
- annotation and technical-gene inclusion rules that can change which genes survive to the final GMT

## Current Anchor Models

These models should be kept in the sweep even if additional models are added later, because they anchor interpretation against current behavior.

- `current_repo_default_harm`: Current default stack in the extractor repo: modern DE workflow plus harmonizome extractor defaults. Workflow=`modern`, backend=`auto`, extractor=`harmonizome`, score=`auto`.
- `current_gtex_noharm_legacy200`: Current GTEx no-harmonizome baseline used in the existing GTEx rerun. Workflow=`modern`, backend=`lightweight`, extractor=`legacy`, score=`auto`.
- `current_gtex_harm_signed250`: Current GTEx harmonizome-style baseline used in the existing GTEx rerun. Workflow=`harmonizome`, backend=`lightweight`, extractor=`harmonizome`, score=`signed_neglog10padj`.

## Step 1i: Parameter-Sweep Models

- proposed parameter-sweep model count: 12

These models vary a small number of parameters around the current GTEx baselines so that any change in GMT membership can be attributed to a specific knob.

- `legacy_filter_sweep`: 3 models. Representative intent: Tests explicit FDR gating before legacy-style aggregation.
- `legacy_size_sweep`: 4 models. Representative intent: Tests a more compact legacy-style set size.
- `legacy_score_sweep`: 5 models. Representative intent: Tests effect-size-first ranking without changing the DE fit.

Most important sweep axes for gene inclusion:

- set size via `top_k` and `gmt_topk_list`
- ranking mode via `score_mode`
- explicit row filters via `padj_max`, `pvalue_max`, and `min_abs_logfc`
- GMT source via full ranked table versus selected rows

## Step 1ii: Defensible Alternative Models

- proposed defensible-model count: 11

These models are not just knob turns. Each one reflects a defensible methodological stance about how RNA DE signatures should be produced for GTEx-like observational tissue data.

- `gene_filter_scope`: 1 models. Representative intent: Separates the effect of gene-filter scope from the effect of group balancing.
- `sample_balancing`: 1 models. Representative intent: Isolates whether deterministic balancing itself materially changes gene inclusion.
- `effect_size_models`: 1 models. Representative intent: Captures a defensible effect-size-first alternative after conservative significance filtering.
- `annotation_filters`: 2 models. Representative intent: Tests whether legacy mismatch is driven partly by harmonizome-mode inclusion of non-protein-coding genes.
- `hybrid_library_models`: 2 models. Representative intent: Separates harmonizome-like ranking/export behavior from harmonizome-mode DE fitting.
- `covariate_design`: 2 models. Representative intent: Tests whether sex and tissue-subsite adjustment is materially reducing age-associated ranking signal.
- `backend_validation`: 2 models. Representative intent: Tests whether the lightweight backend is a material source of divergence from legacy Harmonizome behavior.

## Recommended Execution Order

Run the models in four phases so the early results can prune the larger search space.

1. Anchors: establish the current repo-default, current GTEx no-harmonizome, and current GTEx harmonizome baselines.
2. Focused parameter sweeps: top-k size, score mode, and explicit row-filter sweeps around the baseline models.
3. Workflow design variants: balancing, gene-filter scope, covariate design, and backend validation models.
4. Hybrid library models: cross the most promising DE workflow with the most promising ranking/export behavior from phases 2 and 3.

## Deliverables Written By This Step

- `model_manifest.v1.tsv`: one row per proposed model with explicit workflow and extractor settings
- `model_family_summary.v1.tsv`: counts and rationale by family
- `run_summary.v1.tsv`: compact summary of the proposal contents

## Notes

- This step proposes models only. It does not run the full GTEx extraction pipeline for each model.
- The proposal assumes GTEx metadata currently available in the repo support at least `sex` and `smtsd` as fixed-effect covariates.
- The highest-value early comparison is between the current GTEx no-harmonizome baseline and the harmonizome-style limma/voom validation model, because that separates extractor choices from backend choices.

