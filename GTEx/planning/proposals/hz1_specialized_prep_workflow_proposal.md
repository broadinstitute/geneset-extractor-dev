# Proposal And Implemented Direction: Redefine `HZ1` With Specialized Prep/Workflow Inside The Existing GTEx Model Structure

This note describes the design direction for redefining `HZ1` as a notebook-faithful aging-signature model while still fitting into the existing GTEx output structure.

The current implementation path now delegates the notebook-faithful biology to:

- `geneset_extractors.cli workflows gtex_aging_signatures`

inside `dig-gene-set-extractors`, while the GTEx-local `HZ1` runner remains the thin wrapper that places the outputs under the existing GTEx model tree.

The core idea is:

- keep the current GTEx-style outer model layout
- give `HZ1` its own specialized prep and workflow implementation
- make prep more configurable so future models can request additional behavior without forcing all models through the same assumptions

## Goal

Support a `HZ1` model that:

- runs one broad tissue at a time
- uses notebook-faithful tissue-specific aging-signature logic
- writes outputs alongside the existing GTEx models

while also improving the prep layer so other future models can request:

- different tissue grouping behavior
- different gene-mapping behavior
- different sample-balance behavior
- different prefilter behavior

## Why `HZ1` Needs Specialized Prep/Workflow

`HZ1` should not reuse the standard GTEx prep and workflow path unchanged because its intended logic differs materially from `AB*` and `AC*`.

Notebook-faithful `HZ1` behavior requires:

- GTEx V8 raw gene reads input
- broad-tissue grouping by `SMTS`
- `human_gene_info` Ensembl-to-symbol mapping
- duplicate-Ensembl and duplicate-symbol resolution matching the notebook logic
- balanced age-comparison sampling with `random_state=1`
- limma/voom differential expression per age comparison
- notebook-faithful GMT extraction rules

That means `HZ1` should reuse the outer GTEx model interface and output conventions, but not the current generic prep semantics.

## Recommended High-Level Design

Keep the current model location convention:

- `outputs/genesets/<tissue>/models/HZ1/`

but let `HZ1` use its own specialized prep and workflow stack under that structure.

### Outer shape to preserve

- `commands.md`
- `run.log`
- `workflow/`
- `tissue_extractor/`

### Inner logic to specialize

- sample metadata construction
- gene mapping
- tissue-level counts preparation
- age-comparison balancing
- limma/voom execution
- GMT writing

## Proposed Code Changes

### 1. Split prep responsibilities into a more explicit GTEx prep layer

Instead of treating prep as one fixed process for all models, introduce the idea of:

- a common prep base
- model-specific prep options

Recommended pattern:

- keep:
  - `build_tissue_inputs.py`
  - `build_broad_tissue_inputs.py`
- add a new specialized prep path for notebook-faithful broad-tissue aging signatures, for example:
  - `build_hz1_tissue_inputs.py`

This specialized prep script should:

- accept the GTEx V8 raw reads GCT
- accept sample attributes and subject phenotypes
- accept `human_gene_info`
- group by broad tissue
- construct notebook-faithful sample metadata
- prepare the notebook-style mapped count matrix for one tissue

### 2. Make prep behavior parameter-driven rather than hardcoded

The prep layer should support additional/optional parameters so it can serve more than one model family over time.

Recommended prep parameters:

- `--tissue_grouping detailed|broad`
- `--grouping_column SMTS|SMTSD`
- `--mapping_mode gct_symbols_only|human_gene_info|gtf_annotated`
- `--drop_unmapped_genes`
- `--duplicate_resolution highest_variance`
- `--prefilter_mode none|tissue`
- `--reference_age_bin 20-29`
- `--age_bins ...`

These do not all need to be exposed to every user-facing wrapper immediately, but they should exist in the prep/runtime layer so models can request them declaratively.

### 3. Add model-level prep configuration to planning files

Extend the model planning/configuration so prep expectations are part of model definition.

For example, extend `model_list.tsv` or add a dedicated `hz_model_manifest.tsv` with fields such as:

- `prep_mode`
- `tissue_grouping`
- `mapping_mode`
- `prefilter_mode`
- `duplicate_resolution`
- `random_state`
- `gmt_mode`
- `gmt_sort_by`
- `top_n`

For notebook-faithful `HZ1`, expected values would be approximately:

- `prep_mode = notebook_aging_signature`
- `tissue_grouping = broad`
- `mapping_mode = human_gene_info`
- `prefilter_mode = none`
- `duplicate_resolution = highest_variance`
- `random_state = 1`
- `gmt_mode = top-per-direction`
- `gmt_sort_by = logFC_abs`
- `top_n = 250`

This makes the specialized prep/workflow part of the model definition instead of buried in code.

### 4. Redefine `run_hz_notebook_model.py`

Replace the current `HZ1` implementation with a notebook-faithful per-tissue runner.

Current implemented direction:

- `run_hz_notebook_model.py` calls the `dig` workflow `gtex_aging_signatures`
- `run_hz_notebook_model.py` then calls `convert rna_deg_multi` with notebook-style `top_per_direction` GMT emission

Recommended new responsibilities:

- read one broad-tissue selection from GTEx V8 metadata
- call notebook-faithful prep for that tissue
- run balanced age comparisons for that tissue
- write per-comparison limma results under:
  - `workflow/limma_voom_results/`
- write notebook-faithful GMTs under:
  - `tissue_extractor/gene_set_library_up.gmt`
  - `tissue_extractor/gene_set_library_dn.gmt`
- optionally write an adapter:
  - `tissue_extractor/genesets.gmt`

The authoritative outputs should remain the notebook-faithful up/down GMTs.

### 5. Update `build_genesets.py` so `HZ1` can request its own prep path

Instead of assuming all selected models for a tissue share the same prep contract, `build_genesets.py` should classify models by prep/workflow family.

Recommended behavior:

- `AB*`
  - standard age-binned prep/workflow
- `AC*`
  - continuous-age prep/workflow
- `HZ1`
  - notebook-faithful aging-signature prep/workflow

This means `build_genesets.py` should no longer think only in terms of:

- detailed vs broad tissue prep

It should also think in terms of:

- prep family / workflow family

Current implemented direction:

- `build_genesets.py` treats `HZ1` as a distinct workflow family
- `HZ1` requires `--tissue_granularity broad`
- `HZ1` requires `--human_gene_info`
- `HZ1` uses the broad tissue list `counts_gct` as the raw expression GCT for the `dig` workflow

### 6. Keep output placement consistent with other GTEx models

Even with specialized internals, `HZ1` should still land in the usual GTEx model tree, for example:

- `outputs/genesets/<broad_tissue>/models/HZ1/`

Suggested contents:

- `workflow/`
  - `gtex_aging_sample_metadata.tsv`
  - `gtex_aging_processing_audit.tsv`
  - `limma_voom_results/`
  - optional filtered-count diagnostics
  - `run_manifest.json`
- `tissue_extractor/`
  - `gene_set_library_up.gmt`
  - `gene_set_library_dn.gmt`
  - optional adapter `genesets.gmt`
- `commands.md`
- `run.log`

This keeps `HZ1` visually aligned with the rest of the GTEx outputs even though its internal logic is specialized.

## Recommended Prep Abstraction

To support future model creation cleanly, the code should move toward a prep abstraction with:

### Shared prep responsibilities

- sample/subject metadata loading
- age-bin normalization
- tissue grouping
- sample inclusion/exclusion
- count matrix loading

### Configurable prep features

- mapping source
- grouping level
- duplicate policy
- prefilter policy
- balancing policy

### Model-owned workflow responsibilities

- how comparisons are formed
- whether balancing happens
- DE engine and formula
- GMT extraction logic

This separation would make it much easier to add future notebook-style or specialized models without overloading the standard GTEx prep scripts.

## Recommended Planning Update

Add explicit prep/workflow-family fields to GTEx model planning so that a model can declare:

- what prep family it needs
- what workflow family it needs
- what specialized parameters it uses

This is preferable to relying only on model ID prefix conventions.

## Summary

The recommended update is:

- preserve the current GTEx model/output structure
- redefine `HZ1` to use its own notebook-faithful prep/workflow path
- make prep more parameterized so future models can request specialized behavior
- move model-specific prep/workflow expectations into planning/configuration

That would allow `HZ1` to behave like the new script biologically while still fitting cleanly into the current GTEx codebase and output tree.
