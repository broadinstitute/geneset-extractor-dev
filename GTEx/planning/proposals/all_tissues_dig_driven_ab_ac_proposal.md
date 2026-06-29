# Proposal: Move GTEx `AB*` and `AC*` to a Fully `dig`-Owned Raw-Input Architecture

## Purpose

This proposal revises the earlier all-tissues GTEx redesign target.

The goal is no longer:

- thinner GTEx-local prep plus more `dig`

The goal is now:

- `dig-gene-set-extractors` owns the full runtime path from raw GTEx inputs to final GMT outputs for `AB*` and `AC*`
- `geneset-extractor-dev` becomes an optional wrapper and packaging layer, not a required execution dependency

This change is motivated by provenance and reproducibility. A user with the final provenance JSON should be able to reproduce the analysis with:

- raw GTEx source files
- a `dig-gene-set-extractors` checkout
- the recorded software environment

without needing `geneset-extractor-dev` as part of the actual runtime path.

## Current State

The current GTEx `AB*` and `AC*` flow is:

1. GTEx-local prep reads raw inputs
2. prep writes per-tissue bundles under:
   - `genesets/<tissue>/prepared/`
3. GTEx-local model runners call `dig`
4. `dig` writes DE workflow outputs and GMT outputs

The current prep layer is implemented by:

- [build_tissue_inputs.py](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src/build_tissue_inputs.py)
- [build_broad_tissue_inputs.py](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src/build_broad_tissue_inputs.py)

The current model runners are:

- [run_age_binned_model.py](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src/run_age_binned_model.py)
- [run_continuous_age_model.py](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/src/run_continuous_age_model.py)

This means:

- provenance for `AB*` and `AC*` starts too late
- GTEx-specific metadata shaping is outside `dig`
- reproducing from provenance still depends on `geneset-extractor-dev`

## New Target

The proposed target is:

1. raw GTEx counts GCT
2. raw GTEx sample attributes
3. raw GTEx subject phenotypes
4. `dig` workflow performs GTEx-specific metadata shaping and cohort derivation
5. `dig` workflow performs DE preparation and model execution
6. `dig` converter writes authoritative GMT outputs
7. optional GTEx wrapper copies or reorganizes outputs into the existing layout

In this architecture:

- `dig` is the runtime system of record
- provenance begins at raw GTEx inputs
- any GTEx wrapper is convenience only

## What Must Move into `dig`

To make `geneset-extractor-dev` non-essential for runtime reproduction, the following logic must be moved into `dig`.

### 1. GTEx metadata joining

`dig` must be able to:

- read GTEx sample attributes
- read GTEx subject phenotypes
- join them deterministically
- derive normalized fields such as:
  - `sample_id`
  - `subject_id`
  - `age_bin`
  - `SEX`
  - tissue grouping columns

This cannot remain GTEx-local if provenance-based reproduction is expected to work from `dig` alone.

### 2. GTEx tissue grouping

`dig` must support both GTEx grouping modes:

- detailed tissue
- broad `SMTS` tissue

This should be represented in workflow arguments, not in external prepared bundles.

Suggested arguments:

- `--tissue_granularity detailed|broad`
- `--tissue_column`
- `--tissue_values`
- `--tissue_manifest_tsv` if a stable external mapping table is still needed

### 3. GTEx comparison derivation for `AB*`

For age-binned models, `dig` must derive:

- `20-29` reference comparisons
- comparison IDs
- stable human-readable comparison labels

This currently happens outside `dig` via GTEx-local `comparisons.tsv` generation.

It needs to move into `dig` as either:

- an internal comparison builder, or
- a workflow-specific manifest generator

### 4. GTEx continuous-age configuration for `AC*`

For continuous-age models, `dig` must own:

- continuous-age metadata interpretation
- any covariate setup
- model-family-specific naming and output conventions

This may require either:

- extending `rna_de_prepare` directly, or
- adding a new GTEx-specific continuous-age workflow in `dig`

## Proposed `dig` Workflows

This architecture should not rely only on generic `rna_de_prepare` CLI composition if doing so makes GTEx behavior awkward or under-specified.

The cleanest design is to add dedicated GTEx workflows inside `dig`.

### Workflow A: `gtex_age_binned`

Purpose:

- own the full raw-input-to-DE path for `AB*`

Inputs:

- raw counts GCT
- sample attributes TSV
- subject phenotypes TSV
- model configuration
- tissue grouping configuration

Responsibilities:

- join GTEx metadata
- derive `age_bin`
- derive tissue grouping
- build tissue-stratified age comparisons
- run DE
- emit `deg_long.tsv`
- emit comparison manifest
- emit provenance graph

Then:

- use existing `rna_deg_multi` conversion for GMT generation

### Workflow B: `gtex_continuous_age`

Purpose:

- own the full raw-input-to-DE path for `AC*`

Inputs:

- raw counts GCT
- sample attributes TSV
- subject phenotypes TSV
- model configuration
- tissue grouping configuration

Responsibilities:

- join GTEx metadata
- derive continuous-age fields
- derive tissue grouping
- run per-tissue or stratified continuous-age regression
- emit DE outputs and provenance

Then:

- use existing converter flow for GMT generation

## Execution Shapes

Two execution shapes are still possible, but both must be fully `dig`-owned.

### Option A: One true all-tissues run

`dig` takes the global matrix and all metadata, and performs all selected tissues in one invocation.

Pros:

- strongest provenance story
- one runtime engine
- one consistent metadata derivation path
- most consistent with newer all-dataset `HZ*` models

Cons:

- larger memory and runtime footprint
- output splitting becomes a `dig` concern
- continuous-age implementation may be more complex

### Option B: `dig`-owned per-tissue raw-input runs

`dig` takes raw GTEx inputs plus one selected tissue value per invocation.

Pros:

- easier migration from the current per-tissue layout
- still fully reproducible from `dig`
- lower memory pressure

Cons:

- less elegant than a true all-tissues engine
- repeated metadata parsing per tissue

## Recommended Direction

Recommended target:

- `dig` owns both execution shapes
- start with `dig`-owned per-tissue raw-input runs
- then evaluate whether `AB*` should be promoted to true all-tissues execution

Reason:

- this still removes `geneset-extractor-dev` from the required runtime path
- it is lower risk than forcing one immediate all-tissues implementation
- it preserves easier parity checking against current outputs

So the important distinction is:

- per-tissue execution is acceptable
- GTEx-local prep is not

The core requirement is that the runtime path from raw GTEx input to GMT lives entirely in `dig`.

## Role of `geneset-extractor-dev` After the Redesign

After this redesign, `geneset-extractor-dev` should be optional.

Acceptable responsibilities:

- wrapper shell commands
- model catalog planning
- optional output reshaping into legacy directory layouts
- evaluation workflows downstream of GMT generation

Not acceptable as required runtime responsibilities:

- metadata joining
- tissue cohort definition
- age-bin derivation
- comparison generation
- DE preparation from raw GTEx inputs

If those remain in `geneset-extractor-dev`, then provenance-based reproduction still depends on it.

## Output Compatibility

Even with full `dig` runtime ownership, outputs can still be packaged into the current GTEx structure:

- `genesets/<tissue>/models/<model_id>/workflow/`
- `genesets/<tissue>/models/<model_id>/extractor/`

But this packaging step should be secondary.

The authoritative runtime outputs should be `dig` outputs whose provenance graph already includes:

- raw counts GCT
- sample attributes
- subject phenotypes
- any GTEx-derived internal metadata tables

## Provenance Requirements

For this redesign to satisfy the reproducibility goal, the final provenance should capture:

- raw GTEx input file paths and hashes
- exact `dig` workflow entrypoint and arguments
- intermediate metadata artifacts generated inside `dig`
- repo revision for `dig`
- Python version
- R version
- R package versions used by the DE backend

Optional but recommended:

- exact wrapper command if `geneset-extractor-dev` was used as a convenience layer

The crucial point is that this extra wrapper metadata should not be necessary to reproduce the GMT.

## Required `dig` Changes

Likely additions in `dig-gene-set-extractors`:

- a GTEx metadata-join module
- GTEx age-bin derivation helpers
- GTEx tissue-grouping helpers
- dedicated workflows:
  - `gtex_age_binned`
  - `gtex_continuous_age`
- direct provenance emission from raw GTEx source files
- stable comparison-label generation inside `dig`

Potentially reusable pieces:

- existing DE backends
- existing `rna_deg_multi` conversion
- existing provenance graph machinery

## Comparison with the Current Architecture

### Current prep-based design

Strengths:

- easy to inspect
- stable intermediate bundles
- low-risk for the current per-tissue model runners

Weaknesses:

- provenance starts too late
- GTEx-local prep is runtime-critical
- reproduction depends on two repos, not one
- less consistent with the newer `HZ*` architecture direction

### Fully `dig`-owned design

Strengths:

- provenance can begin at raw source files
- one runtime system of record
- stronger reproducibility story
- cleaner separation between runtime engine and optional wrappers

Weaknesses:

- larger migration effort
- more GTEx-specific code enters `dig`
- initial parity validation will take time

## Migration Strategy

This should be rolled out as a new execution architecture, not as a silent rewrite.

Suggested stages:

1. implement `dig` GTEx metadata joining and tissue derivation
2. implement `dig` `gtex_age_binned`
3. validate `AB1` against the current prep-based path
4. implement `dig` `gtex_continuous_age`
5. validate `AC1` against the current prep-based path
6. only then mark the old prep-based path as legacy

During migration, `geneset-extractor-dev` can still call the new `dig` workflows so the user-facing CLI remains stable.

## Recommendation

If the real goal is:

- provenance-driven reproducibility from raw data
- `dig` as the system of record
- no required dependency on `geneset-extractor-dev`

then the proposal should explicitly target a full runtime migration into `dig`.

That means the earlier hybrid design is not sufficient.

The correct target is:

- raw GTEx input handling in `dig`
- GTEx metadata shaping in `dig`
- GTEx model execution in `dig`
- GTEx provenance in `dig`
- optional wrapper logic only in `geneset-extractor-dev`

## Bottom Line

Yes, `AB*` and `AC*` can be redesigned so that a user with the provenance JSON does not need `geneset-extractor-dev` to reproduce the GMT.

But that requires a stronger change than simply removing `prepared/`.

It requires moving the GTEx-specific runtime logic itself into `dig`, and treating `geneset-extractor-dev` as optional packaging and orchestration rather than a required execution layer.
