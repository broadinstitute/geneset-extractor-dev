# Proposal: Unified GTEx Model-Prep Abstraction

This note proposes a prep abstraction that would allow:

- `AB*`
- `AC*`
- notebook-faithful `HZ1`

to become special cases of one broader GTEx model-prep system.

## Goal

Replace the current model-specific prep branching with a more explicit prep framework that separates:

1. shared prep responsibilities
2. configurable prep transforms
3. model-specific workflow requirements

The intent is not to force all models through one identical prep script. The intent is to make them all instances of a single prep architecture with explicit model-selected behavior.

## Current Situation

Today:

- `AB*` and `AC*` share a prepared tissue bundle under:
  - `outputs/genesets/<tissue>/prepared/`
- `AB*` additionally depends on:
  - `comparisons.tsv`
- `AC*` derives continuous-age behavior later in workflow
- notebook-faithful `HZ1` would need a different prep path:
  - GTEx V8 raw reads
  - broad `SMTS` tissue grouping
  - `human_gene_info` mapping
  - notebook-style balancing assumptions

So the current code already has the beginnings of shared prep, but only for the standard GTEx models.

## Proposed Abstraction

Define prep as three layers.

### Layer 1: Shared prep base

This layer is responsible for universally useful tasks:

- loading counts input
- loading sample metadata
- loading subject metadata
- resolving sample identifiers
- normalizing age and sex labels
- selecting one tissue cohort
- writing canonical sample metadata

This layer should not decide:

- how genes are mapped
- whether comparisons are emitted
- whether continuous-age metadata is needed
- whether notebook-style balancing should happen

It should only define a canonical prepared cohort.

### Layer 2: Configurable prep transforms

This layer applies optional transforms selected by model configuration.

Recommended prep transform axes:

- `tissue_grouping`
  - `detailed`
  - `broad`

- `mapping_mode`
  - `gct_symbols_only`
  - `human_gene_info`
  - `gtf_annotated`

- `duplicate_resolution`
  - `none`
  - `highest_variance`
  - `last`

- `prefilter_mode`
  - `none`
  - `tissue`

- `comparison_manifest_mode`
  - `none`
  - `age_binned`

- `count_matrix_mode`
  - `raw_selected_samples`
  - `mapped_symbol_matrix`

This layer should produce a prepared bundle shaped consistently enough that the workflow layer can consume it.

### Layer 3: Model-specific workflow prep outputs

This layer emits the extra files required by each workflow family.

Examples:

- `AB*`
  - requires:
    - `comparisons.tsv`

- `AC*`
  - requires:
    - no comparison manifest at prep time
    - continuous-age metadata can be derived later

- notebook-faithful `HZ1`
  - requires:
    - broad tissue
    - notebook-faithful mapped counts
    - notebook-style age-comparison semantics
    - optional prefilter policy

So the prep system should be able to emit:

- shared outputs for all models
- plus model-family-specific prep artifacts

## Proposed Prepared Bundle Contract

### Core prepared outputs

Always write:

- `prepared/tissue_counts.tsv`
- `prepared/sample_metadata.tsv`
- `prepared/prepare_summary.json`
- `prepared/naming_reference.md`

These should be the canonical base prepared outputs.

### Optional prepared outputs

Write only when required by the selected prep/workflow family:

- `prepared/comparisons.tsv`
- `prepared/continuous_metadata.tsv`
- `prepared/mapping_audit.tsv`
- `prepared/filter_audit.tsv`
- `prepared/notebook_prep_manifest.json`

This keeps the prepared bundle extensible without making every model depend on every file.

## Proposed Planning/Configuration Fields

To make models special cases of the prep system, model planning should include prep-oriented fields.

Recommended fields:

- `prep_family`
- `tissue_grouping`
- `mapping_mode`
- `duplicate_resolution`
- `prefilter_mode`
- `comparison_manifest_mode`
- `count_matrix_mode`

Possible examples:

### `AB1`

- `prep_family = standard_gtex`
- `tissue_grouping = detailed` or `broad`
- `mapping_mode = gct_symbols_only`
- `duplicate_resolution = none`
- `prefilter_mode = none`
- `comparison_manifest_mode = age_binned`
- `count_matrix_mode = raw_selected_samples`

### `AC1`

- `prep_family = standard_gtex`
- `tissue_grouping = detailed` or `broad`
- `mapping_mode = gct_symbols_only`
- `duplicate_resolution = none`
- `prefilter_mode = none`
- `comparison_manifest_mode = none`
- `count_matrix_mode = raw_selected_samples`

### notebook-faithful `HZ1`

- `prep_family = notebook_aging_signature`
- `tissue_grouping = broad`
- `mapping_mode = human_gene_info`
- `duplicate_resolution = highest_variance`
- `prefilter_mode = none` or `tissue`
- `comparison_manifest_mode = age_binned`
- `count_matrix_mode = mapped_symbol_matrix`

## Proposed Code Shape

### New prep coordinator

Add a prep coordinator such as:

- `src/build_gtex_model_prep.py`

This would:

- read prep-related configuration
- choose the tissue grouping path
- choose the mapping path
- choose which optional artifacts to emit
- write the prepared bundle

### Reuse lower-level helpers

Current scripts should become lower-level helpers or prep-family implementations:

- `build_tissue_inputs.py`
- `build_broad_tissue_inputs.py`
- future:
  - `build_hz1_tissue_inputs.py`

Rather than each being a top-level prep concept on its own, they would become implementations selected by the prep coordinator.

### `build_genesets.py`

`build_genesets.py` should evolve from:

- deciding only between detailed and broad tissue prep

to:

- resolving model IDs
- grouping selected models by prep family
- requesting the appropriate prepared bundle configuration
- then dispatching workflows

This is the point where `AB`, `AC`, and `HZ1` become special cases of one broader prep system.

## Workflow Implications

The workflows would still remain different.

That is expected.

The benefit of this abstraction is not that all workflows become the same. It is that they receive prepared inputs through one coherent prep interface.

Examples:

- `AB*`
  - consumes:
    - `tissue_counts.tsv`
    - `sample_metadata.tsv`
    - `comparisons.tsv`

- `AC*`
  - consumes:
    - `tissue_counts.tsv`
    - `sample_metadata.tsv`

- notebook-faithful `HZ1`
  - consumes:
    - notebook-faithful mapped `tissue_counts.tsv`
    - notebook-faithful `sample_metadata.tsv`
    - `comparisons.tsv` or equivalent age-comparison definition

## Benefits

This abstraction would:

- make model prep requirements explicit
- reduce hidden assumptions in `build_genesets.py`
- allow future models to request specialized behavior cleanly
- preserve sharing where it already makes sense
- avoid pretending all models need the same prep internals

## Migration Strategy

### Phase 1

Add prep configuration fields to planning files and implement a prep coordinator while leaving existing helpers mostly intact.

### Phase 2

Refactor:

- `AB*`
- `AC*`
- `HZ1`

to declare prep requirements through configuration rather than ad hoc branching.

### Phase 3

Deprecate direct use of the current prep scripts as top-level concepts if the coordinator fully subsumes them.

## Summary

Yes, `AB`, `AC`, and notebook-faithful `HZ1` can become special cases of one broader prep system, but only if prep is treated as:

- one shared base
- plus explicit configurable transforms
- plus workflow-specific prepared outputs

That is the right abstraction level for future GTEx model growth.
