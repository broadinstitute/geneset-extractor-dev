# Proposal: HuBMAP `HZ*` Integration From ASCT+B Notebook-Replica Scripts

This note proposes how to integrate the standalone notebook-replica scripts:

- `notebooks_adapted/build_hubmap_asctb_gmt.py`
- `notebooks_adapted/build_hubmap_asctb_augmented_gmt.py`

into a new `geneset-extractor-dev/HuBMAP/` pipeline area.

## Conclusion

The clean integration shape is very similar to the recent LINCS_L1000 and MoTrPAC `HZ` models:

- all-dataset models
- no tissue-specific run architecture
- notebook-replica workflow remains authoritative for preprocessing and intermediate table construction
- `dig-gene-set-extractors` should be the authoritative GMT writer
- same outer model layout as the other integrated `HZ` models

Because there are two distinct notebook-replica workflows, the recommended model design is:

- `HZ1`
  - base ASCT+B
- `HZ2`
  - augmented ASCT+B

## Why Two Models Instead Of One

The two scripts have different starting points and different biological logic:

### Base ASCT+B

- starts from raw or prepared ASCT+B tables
- builds cell-type marker sets from ASCT+B tables plus `human_gene_info`

### Augmented ASCT+B

- starts from an existing `gene_attribute_matrix.txt.gz`
- queries or loads Geneshot augmentations
- constructs augmented cell-type gene sets

These are too different to hide behind one model ID unless a second required selector is added. The cleaner model policy is:

- `HZ1` = base ASCT+B
- `HZ2` = augmented ASCT+B

## Proposed Repository Layout

Use the existing extractor root:

- `geneset-extractor-dev/HuBMAP/`

with:

- `src/`
- `run/`
- `planning/`
- `outputs/`

## Proposed Planning Files

Under `geneset-extractor-dev/HuBMAP/planning/`:

- `model_list.tsv`
- `model_manifest.tsv`
- `pipeline_inputs.md`
- this proposal

No tissue list is needed because the initial `HZ*` models are all-dataset runs.

## Proposed Model Registry

`model_list.tsv`:

- `HZ1`
  - `model_family=hz_released_asctb`
  - `description=hubmap_asctb_harmonizome_notebook_style`
  - `enabled=false`
- `HZ2`
  - `model_family=hz_released_asctb`
  - `description=hubmap_asctb_augmented_harmonizome_notebook_style`
  - `enabled=false`

## Proposed Inputs

### `HZ1` base ASCT+B

Required:

- `--raw_asctb_dir inputs/HuBMAP/ASCT+B/v2.2`
- `--human_gene_info inputs/human_gene_info`

Optional or model-configurable:

- `--prepared_asctb_dir`
- `--limit_tables`
- `--overwrite_prepared`

### `HZ2` augmented ASCT+B

Required:

- `--input_matrix`
  - e.g. `outputs_hubmap/gene_attribute_matrix.txt.gz`
- `--human_gene_info inputs/human_gene_info`

Likely optional:

- `--gene_info`
- `--gene_csv`
- `--attribute_tsv`
- `--limit_terms`
- `--geneshot_url`
- `--use_existing_augmented_tsv`

### Shared

- `--dig_dir`
- `--out_root`
- provenance mirror options

## Proposed Runtime Shape

Add:

- `src/build_hubmap_asctb_hz1.py`
- `src/build_hubmap_asctb_hz1.md`
- `src/build_hubmap_asctb_augmented_hz2.py`
- `src/build_hubmap_asctb_augmented_hz2.md`

These should be thin wrappers around the standalone scripts, following the same pattern used for:

- MoTrPAC `HZ1`
- LINCS_L1000 `HZ1` and `HZ2`

Add a shared model runner:

- `src/run_hubmap_hz_model.py`

and a top-level entrypoint:

- `src/build_hubmap_genesets.py`
- `run/build_hubmap_genesets.sh`

## Proposed Output Layout

The all-dataset output tree should be:

- `hubmap_outputs/genesets/all_signatures/models/HZ1/`
- `hubmap_outputs/genesets/all_signatures/models/HZ2/`

Each model should write:

- `workflow/`
- `tissue_extractor/`
- `commands.md`
- `run.log`

Even though HuBMAP is not tissue-scoped here, using `all_signatures` keeps it consistent with the LINCS_L1000 `HZ` pattern.

## Use Of `dig`

`dig` should be the authoritative GMT writer, not the standalone scripts.

Recommended pattern:

1. run the notebook-replica workflow to build the processed/intermediate table
2. transform that intermediate table into a dig-compatible signed term-gene table
3. use `dig` to write:
   - `genesets.gmt`
   - `geneset.tsv`
   - `geneset.full.tsv`
   - metadata and provenance JSON

The best current fit is likely reuse of the existing:

- `convert signed_term_gene`

added earlier for MoTrPAC/LINCS-style signed term-gene inputs.

## Expected Intermediate Tables

### `HZ1` base ASCT+B

The standalone script builds cell-type marker relationships from ASCT+B tables and `human_gene_info`.

The integration should emit an intermediate signed table like:

- `term`
  - cell type / anatomical structure label
- `gene_id`
  - likely same as `gene_symbol` for this workflow
- `gene_symbol`
- `score`
  - constant positive score or notebook-derived weight if present
- `sign`
  - likely `1` only, unless the notebook meaningfully distinguishes positive and negative sets

Important implication:

- if the base ASCT+B workflow only emits unsigned positive memberships, then `dig` will still be authoritative, but the converter path should emit one set per term rather than signed up/down pairs
- if the existing `signed_term_gene` converter is reused, this may require setting all `sign=1`

### `HZ2` augmented ASCT+B

The standalone script creates augmented memberships from:

- existing base matrix
- Geneshot augmentation scores
- final threshold/cap logic

The integration should emit an intermediate table like:

- `term`
- `gene_id`
- `gene_symbol`
- `score`
  - augmentation-weight or inclusion score
- `sign`
  - probably `1` only unless the augmented workflow uses directional signs

This means HuBMAP may differ from LINCS and MoTrPAC in one important way:

- the HuBMAP models may be fundamentally unsigned membership libraries

If so, there are two implementation options:

### Option A: Reuse `signed_term_gene`

- set all `sign = 1`
- let `dig` emit one positive set per term
- use naming without directional suffixes if needed

### Option B: Add A Small Unsigned Term-Gene Converter

If HuBMAP output naming or semantics do not fit `signed_term_gene` cleanly, add:

- `convert unsigned_term_gene`

This would likely be a very small companion converter, but it should only be added if `signed_term_gene` cannot express the desired output without awkward hacks.

## Proposed Model Manifest

`model_manifest.tsv` should include workflow-specific knobs:

### `HZ1`

- `workflow_min_gmt_size`
- `workflow_limit_tables`
- `workflow_overwrite_prepared`

### `HZ2`

- `workflow_limit_terms`
- `workflow_use_existing_augmented_tsv`
- `workflow_geneshot_url`
- `workflow_gmt_min_size`

## Companion Tracking Files

Because the implementation will adapt notebook-replica scripts, add tracking notes:

- `src/build_hubmap_asctb_hz1.md`
- `src/build_hubmap_asctb_augmented_hz2.md`

These should document:

- source script path
- copied or wrapped logic
- any intentional deviations

## Recommendation

Implement a new HuBMAP pipeline with:

- `HZ1` = base ASCT+B
- `HZ2` = augmented ASCT+B

using the same outer pattern as the LINCS_L1000 `HZ` models:

- all-signatures output root
- notebook-replica workflow under `workflow/`
- `dig` as the authoritative GMT writer under `tissue_extractor/`

The one design question to resolve during implementation is whether HuBMAP can cleanly reuse `signed_term_gene` with positive-only memberships, or whether it deserves a tiny unsigned companion converter.
