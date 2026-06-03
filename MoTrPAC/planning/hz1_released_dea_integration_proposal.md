# Proposal: MoTrPAC `HZ1` Integration From Released DEA Tables

This note proposes how to integrate `notebooks_adapted/build_motrpac_rat_endurance_gmt.py` into the current MoTrPAC pipeline as model `HZ1`.

The main conclusion is that this requires a different inner workflow from the current MoTrPAC `TR1` and `TW1` models, but it can still be packaged in the same outer model-output format.

So the target should be:

- same outer pipeline format as the other MoTrPAC models
- specialized all-tissues inner workflow for `HZ1`

This is different from the current raw-count models in one important way:

- the authoritative biological workflow should remain the standalone notebook-replica logic up to the processed term-gene table
- the pipeline wrapper should adapt around it while preserving the same top-level model layout
- `dig-gene-set-extractors` should be the authoritative GMT writer

## Why This Needs A Separate Model Shape

The current MoTrPAC pipeline assumes:

- one selected tissue at a time
- raw counts as the starting point
- prepared bundle under `genesets/<tissue>/prepared/`
- differential expression run inside the pipeline
- per-comparison DEG tables converted by `dig`

The standalone notebook-replica script does something materially different:

- starts from released MoTrPAC DEA tables under one directory
- loads all tissues together in one run
- combines timewise and training DEA products
- applies notebook-style feature-to-gene and symbol mapping
- thresholds by sign of `logFC`
- writes notebook-style GMT libraries directly
- writes one combined output directory, not one tissue subtree per run

Because of that, `HZ1` for MoTrPAC should not be forced into the existing tissue-specific prepared-bundle architecture internally.

However, it can still be made to look like the existing models externally.

## Desired Integration Goal

`HZ1` should sit alongside the other MoTrPAC models and expose the same broad file categories:

- `models/HZ1/workflow/`
- `models/HZ1/tissue_extractor/`
- `models/HZ1/commands.md`
- `models/HZ1/run.log`

The specialized part should be inside the runner implementation, not in the user-facing output layout.

## Recommended Model Definition

Add a new model:

- `HZ1`
- `model_family = hz_released_dea`
- description such as:
  - `harmonizome_notebook_style_released_dea_all_tissues`

This model should be treated as:

- one run over all tissues at once
- no tissue selector required or used
- no standard tissue-specific `prepared/` bundle contract internally

But it should still be emitted under the same model-oriented directory shape as the rest of the pipeline.

## Recommended Runtime Shape

Add a dedicated runtime path instead of reusing `build_motrpac_tissue_inputs.py` plus the current model runners.

### New runner

Add:

- `geneset-extractor-dev/MoTrPAC/src/run_motrpac_hz_released_dea_model.py`

Responsibilities:

- accept the released MoTrPAC DEA inputs and mapping inputs
- reproduce the standalone notebook-replica script cell-for-cell as closely as possible
- write outputs into a pipeline-owned model directory
- optionally emit additional adapter files for consistency with the existing pipeline

### Top-level orchestrator changes

Update:

- `geneset-extractor-dev/MoTrPAC/src/build_motrpac_genesets.py`

Behavior:

- if `HZ1` is selected, bypass tissue iteration
- run `run_motrpac_hz_released_dea_model.py` exactly once
- write outputs under a model-level root that mirrors the current model structure

Suggested output root:

- `motrpac_outputs/genesets/all_tissues/models/HZ1/`

That keeps the output alongside the existing pipeline while honestly reflecting that `HZ1` is not tissue-scoped.

## Inputs For `HZ1`

The standalone script currently expects:

- `--feature-annot`
- `--dea-dir`
- `--mapping-file`
- `--output-dir`

Optional notebook-style extras:

- `--gene-info`
- `--gene-csv`
- `--mode`
- `--gmt-format`
- `--padj-max`
- `--min-genes`

For pipeline integration, the minimal required inputs should be:

- `--feature_annot`
- `--dea_dir`
- `--mapping_file`
- `--out_root`
- `--dig_dir`

Optional passthroughs:

- `--padj_max`
- `--min_genes`
- `--mode`
- `--gmt_format`
- `--provenance_mirror_local_prefix`
- `--provenance_mirror_remote_prefix`

## Proposed Output Layout

Suggested authoritative outputs:

- `motrpac_outputs/genesets/all_tissues/models/HZ1/workflow/`
- `motrpac_outputs/genesets/all_tissues/models/HZ1/tissue_extractor/`
- `motrpac_outputs/genesets/all_tissues/models/HZ1/commands.md`
- `motrpac_outputs/genesets/all_tissues/models/HZ1/run.log`

Within `workflow/`:

- `motrpac_processed.tsv`
- `motrpac_processing_audit.tsv`
- optional additional notebook outputs depending on mode

Within `tissue_extractor/`:

- `genesets.gmt`
- `geneset.tsv`
- `geneset.full.tsv`
- `geneset.meta.json`
- `geneset.provenance.json`

Optional adapter files for pipeline consistency:

- `signature_summary.tsv`
- `run_manifest.json`

The notebook-replica workflow outputs can still remain under `workflow/` for audit and comparison, but `dig` should write the authoritative GMT under `tissue_extractor/`.

This gives `HZ1` the same broad outer shape as:

- `TR1`
- `TW1`

even though the biological workflow inside `workflow/` is different.

## Use Of `dig-gene-set-extractors`

`dig` should be the authoritative GMT writer for the integrated pipeline model.

Recommended use:

- command/provenance conventions
- authoritative GMT emission
- metadata and provenance artifacts

Recommended implementation:

- transform `motrpac_processed.tsv` into a dig-compatible signed term-gene table
- use a dedicated dig converter for that signed table

Reason:

- the standalone script does not start from one DEG table per signature in the same way as GTEx `HZ1`
- it combines released DEA products into a signed term-gene table
- a dedicated dig converter can preserve that logic more faithfully than forcing the data through `rna_deg`

## Relation To The Existing MoTrPAC Models

Current models:

- `TR1`
  - tissue-specific
  - raw-count based
  - one DEG model per tissue
- `TW1`
  - tissue-specific
  - raw-count based
  - one DEG model per `tissue × sex × timepoint`

Proposed `HZ1`:

- all tissues at once
- released-DEA based
- notebook-style GMT library builder

So `HZ1` should be modeled as a parallel family, not a variant of `TR1` or `TW1`.

But it should still be presented through the same outer model layout conventions as `TR1` and `TW1`.

## Minimal File Changes If Implemented

1. Update `planning/model_list.tsv`

- add `HZ1`
- set `model_family = hz_released_dea`

2. Update `planning/model_manifest.tsv`

- either add an `HZ1` row with notebook-style parameters
- or create a separate `hz_model_manifest.tsv` if the settings are too different from `TR1` and `TW1`

3. Add:

- `src/run_motrpac_hz_released_dea_model.py`

This should be a pipeline wrapper around the standalone notebook-replica logic.

4. Update:

- `src/build_motrpac_genesets.py`

Add a branch for:

- `model_family == "hz_released_dea"`

5. Update:

- `run/build_motrpac_genesets.sh`

Expose the new required input flags for `HZ1`.

## Companion Change-Tracking Requirement

Because the standalone logic is being adapted from:

- `notebooks_adapted/build_motrpac_rat_endurance_gmt.py`

the implementation should include a companion markdown note, for example:

- `geneset-extractor-dev/MoTrPAC/src/run_motrpac_hz_released_dea_model.md`

This file should record:

- source script path
- which parts were copied or wrapped
- any intentional deviations from the standalone script

## Recommendation

Implement `HZ1` as a separate all-tissues model family with a dedicated runner that wraps the standalone notebook-replica logic, transforms the processed output into a dig-compatible signed term-gene table, and lets `dig-gene-set-extractors` write the authoritative GMT output.

That is the safest way to preserve the notebook behavior while still integrating the model into the MoTrPAC pipeline tree, command surface, and output layout conventions.
