# Tissue Prep Comparison: Current GTEx Code vs `GTEx_AgeComparison_Tissue_Sigs.ipynb`

This note compares the current GTEx tissue-preparation code in:

- `geneset-extractor-dev/GTEx/src/build_tissue_inputs.py`
- `geneset-extractor-dev/GTEx/src/build_broad_tissue_inputs.py`

to the notebook:

- `GTEx_AgeComparison_Tissue_Sigs.ipynb`

## What Now Matches More Closely

The addition of `build_broad_tissue_inputs.py` closes the biggest earlier gap.

- The notebook starts from one global GTEx matrix and groups samples by broad tissue using `SMTS`.
- The current GTEx code can now also start from one global GTEx matrix and build one prepared bundle for a broad `SMTS` tissue such as:
  - `Adipose Tissue`
  - `Blood Vessel`
  - `Brain`

So the current pipeline can now mirror the notebook's broad-tissue cohort definition much more closely than the older detailed-tissue-only path.

## Current Prep Modes

### Detailed-tissue prep

- `build_tissue_inputs.py`
- input: one per-tissue GTEx `gct.gz` file
- grouping level: effectively one detailed tissue at a time

### Broad-tissue prep

- `build_broad_tissue_inputs.py`
- input: one full GTEx counts `gct.gz` file
- grouping level: one broad `SMTS` tissue at a time

The broad-tissue mode is the appropriate comparison point for the notebook.

## Remaining Differences

### Gene filtering before DE

- The notebook performs gene preprocessing before any differential expression step:
  - maps Ensembl IDs to gene symbols using `Homo_sapiens.gene_info`
  - drops genes without a mapping
  - applies `filter_by_expr` per tissue before building age comparisons
- The current prep scripts do none of that during prep.
- Both current prep scripts keep all rows from the input GCT and write:
  - `gene_id`
  - `gene_symbol`
  - retained sample columns

So gene filtering and symbol cleanup are still lighter in the current prep code than in the notebook.

### Comparison construction

- The notebook directly constructs balanced age-comparison sample sets by random subsampling each comparison group to the same size as the `20-29` reference group, using `random_state=1`.
- The current prep scripts only write a `comparisons.tsv` manifest.
- They do not subsample or balance samples at prep time.

So the notebook still makes comparison-specific sampled cohorts during prep, while the current prep code only defines which comparisons are eligible.

### Minimum sample threshold

- The notebook requires at least `3` samples in the `20-29` reference group and at least `3` in each comparison age group.
- The current prep scripts default to `2` using `--min_samples_per_group`.

This can be made closer by running prep with `--min_samples_per_group 3`, but the default still differs.

### Where balancing and filtering happen

- In the notebook, balancing and expression filtering happen during prep and comparison generation.
- In the current pipeline, those decisions are mostly deferred to downstream model-specific steps.

So even with broad `SMTS` prep, the current design is still more modular and less notebook-like at the prep stage itself.

### Output shape

- The notebook directly writes per-comparison DE result TSVs and one metadata table describing selected case/control sample IDs.
- The current prep scripts write a reusable prepared bundle:
  - `tissue_counts.tsv`
  - `sample_metadata.tsv`
  - `comparisons.tsv`
  - `prepare_summary.json`
  - `naming_reference.md`

So the notebook still blends prep and DE generation more tightly than the current GTEx code.

## Differences That No Longer Matter As Much

### Input scope

This used to be a major difference:

- notebook: one global matrix
- current code: one per-tissue file only

That is no longer true for broad-tissue analysis, because `build_broad_tissue_inputs.py` now supports the global-matrix path directly.

### Tissue grouping

This also used to be a major difference:

- notebook: grouped by `SMTS`
- current code: effectively detailed tissues only

That gap is now largely closed for broad-tissue runs.

## Summary

With the new broad `SMTS` prep path, the current GTEx code now matches the notebook much more closely on:

- using the full GTEx matrix
- defining broad tissue cohorts from `SMTS`
- preparing one broad tissue at a time

The main remaining differences are:

- no prep-time gene symbol remapping/drop step
- no prep-time `filter_by_expr`
- no prep-time balanced subsampling of case/control age groups
- a lower default minimum sample threshold
- reusable prepared-bundle outputs instead of direct DE-result outputs

So the broad-tissue prep addition removes the biggest cohort-definition mismatch, but the notebook is still more opinionated about filtering and balancing during prep itself.
