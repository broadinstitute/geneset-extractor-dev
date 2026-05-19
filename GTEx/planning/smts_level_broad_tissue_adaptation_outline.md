# Outline: Adapting The Current GTEx Pipeline To Support `SMTS`-Level Broad Tissues

This note outlines how to adapt the current GTEx prep/build code so it can produce broad tissue gene sets such as:

- `AdiposeTissue`
- `BloodVessel`
- `Brain`

instead of only detailed tissues such as:

- `adipose_subcutaneous`

## Goal

Support gene-set generation at the broad `SMTS` tissue level, while preserving the current CLI-first GTEx workflow structure.

## Why The Current Pipeline Does Not Already Do This

The current pipeline expects one counts matrix per tissue input. In practice that means:

- one detailed tissue file
- one prepared bundle
- one tissue-specific model run

Broad `SMTS` tissues are not currently representable from a single detailed-tissue counts file. For example:

- `AdiposeTissue` would need samples from multiple detailed tissues, not just `Adipose - Subcutaneous`

## Required Input Change

To support broad tissues, the pipeline needs access to either:

1. one global GTEx counts matrix covering all tissues

or

2. a merged broad-tissue counts matrix built from multiple detailed-tissue inputs

The cleanest option is:

- use the global GTEx counts matrix
- derive broad tissue cohorts using sample metadata and `SMTS`

## High-Level Adaptation Plan

### 1. Add a broad-tissue prep mode

Extend prep so it can build one prepared bundle for a broad `SMTS` tissue rather than a single detailed file.

This prep mode would:

- read the full GTEx counts matrix
- read sample metadata and subject metadata
- select samples whose `SMTS` matches the requested broad tissue
- write a prepared bundle for that broad tissue

Outputs would remain conceptually similar:

- `tissue_counts.tsv`
- `sample_metadata.tsv`
- `comparisons.tsv`
- `prepare_summary.json`

### 2. Add a broad-tissue catalog

Create a planning/config file listing supported broad tissues, for example:

- `broad_tissue_list.tsv`

Fields could include:

- `tissue_id`
- `tissue_label`
- `metadata_group_column`
- `metadata_group_value`
- `enabled`

Example:

- `adipose_tissue`
- `Adipose Tissue`
- `SMTS`
- `Adipose Tissue`

### 3. Keep the existing prepared-bundle contract

The easiest way to preserve the current downstream runners is:

- make broad-tissue prep emit the same prepared-bundle file names as the current detailed-tissue prep

That way:

- `run_age_binned_model.py`
- `run_continuous_age_model.py`
- `run_cfde_notebook_model.py`

can continue to operate on prepared bundles without large structural changes.

### 4. Add a way to choose tissue granularity

At the top-level build interface, add a selector such as:

- `--tissue_granularity detailed|broad`

Possible behavior:

- `detailed`
  - current `tissue_list.tsv` behavior
- `broad`
  - use `broad_tissue_list.tsv`
  - require the global counts matrix or a broad-tissue source

### 5. Update tissue prep implementation

The current prep script:

- `build_tissue_inputs.py`

would need one of these approaches:

1. add a new mode to the existing script

or

2. add a separate GTEx-local script such as:

- `build_broad_tissue_inputs.py`

The separate-script option is cleaner if you want to keep the detailed-tissue path simple.

### 6. Define how broad-tissue IDs should look

Use normalized `SMTS`-style IDs, for example:

- `adipose_tissue`
- `blood_vessel`
- `brain`

This should be distinct from detailed-tissue IDs such as:

- `adipose_subcutaneous`
- `artery_tibial`

### 7. Keep model families reusable

Once the prepared bundle exists, most model families can still be reused:

- `AB*` age-binned models
- `AC*` continuous-age models
- `CFDE1`

The main difference is the sample cohort being analyzed.

### 8. Update downstream discovery assumptions

The rest of the pipeline should continue to work if broad tissues are just additional tissue directories under:

- `gtex_outputs/genesets/<tissue_id>/`

That means:

- `run_pigean.sh`
- `run_eaggl.sh`
- summary scripts

should not need major changes as long as they treat broad tissue IDs like any other tissue directory.

### 9. Decide whether to expose broad tissues alongside detailed tissues

There are two reasonable designs:

1. one unified tissue catalog containing both broad and detailed tissues

2. separate catalogs
   - `tissue_list.tsv`
   - `broad_tissue_list.tsv`

The second option is easier to reason about and safer operationally.

## Minimal Practical Implementation

The smallest useful implementation would be:

1. add `broad_tissue_list.tsv`
2. add a GTEx-local prep script for broad tissues using the global GTEx matrix
3. add `--tissue_granularity broad`
4. keep downstream model runners unchanged by emitting the same prepared-bundle structure

## Summary

To support `SMTS`-level broad tissues, the key change is not in the model runners. It is in the prep/input layer.

You need:

- a data source that spans multiple detailed tissues
- a prep step that selects samples by `SMTS`
- a broad-tissue catalog

Once that exists, the current model build flow can mostly be reused on top of the prepared broad-tissue bundle.
