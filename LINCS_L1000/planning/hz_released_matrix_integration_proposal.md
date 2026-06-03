# Proposal: LINCS_L1000 `HZ*` Integration From Released Matrices

This note proposes how to integrate the standalone notebook-replica scripts:

- `notebooks_adapted/build_lincs_l1000_chempert_gmt_only.py`
- `notebooks_adapted/build_lincs_l1000_crisprko_gmt_only.py`

into a new `geneset-extractor-dev/LINCS_L1000/` pipeline area.

## Conclusion

This needs a proposal-first integration rather than immediate code changes because it differs from the current MoTrPAC `HZ1` adaptation in several important ways:

1. there is no existing `LINCS_L1000` pipeline tree in this checkout
2. there are two distinct notebook-replica workflows
3. both are all-dataset GMT builders rather than tissue- or sample-scoped models
4. the current request says "model name HZ1", but there are two initial models

So the first thing to resolve is the model-family shape.

## Major Differences From MoTrPAC `HZ1`

MoTrPAC `HZ1` could be added to an already-existing extractor area:

- `geneset-extractor-dev/MoTrPAC/`

It also had one new notebook-style model to integrate.

For LINCS L1000:

- there is no current `geneset-extractor-dev/LINCS_L1000/`
- there are two separate workflows:
  - chemical perturbation consensus signatures
  - CRISPR knockout consensus signatures
- each workflow starts from a released matrix and directly builds a combined GMT

That means the integration has to define:

- a new extractor root
- a new planning/model registry
- a policy for whether these are:
  - one model family with two model IDs
  - or one `HZ1` model with a required assay selector

## Recommendation

Use a new model family `HZ*` with two initial model IDs:

- `HZ1`
  - `chempert`
- `HZ2`
  - `crisprko`

Reason:

- the two workflows are materially different
- they have different primary input matrices
- they apply different notebook logic
- using one model ID for both would make commands and manifests less explicit

If you want one name family only, `HZ*` still gives that. It avoids overloading `HZ1` to mean two incompatible input contracts.

## Alternative If You Insist On A Single `HZ1`

If you want only `HZ1`, the pipeline could support:

- `--models HZ1`
- plus a required selector like:
  - `--hz_assay chempert`
  - or `--hz_assay crisprko`

This is possible, but weaker than separate model IDs because:

- manifests become less descriptive
- outputs for two biologically different workflows are hidden behind one model ID
- command reproducibility is less obvious

So the recommended design remains:

- `HZ1` = chempert
- `HZ2` = crisprko

## Proposed Repository Layout

Create:

- `geneset-extractor-dev/LINCS_L1000/`

with:

- `src/`
- `run/`
- `planning/`
- `outputs/`

## Proposed Planning Files

Under `geneset-extractor-dev/LINCS_L1000/planning/`:

- `model_list.tsv`
- `model_manifest.tsv`
- `pipeline_inputs.md`
- this proposal file

No tissue list is needed for the initial `HZ*` models because they are all-dataset runs.

## Proposed Model Registry

### Recommended

`model_list.tsv`:

- `HZ1`
  - `model_family=hz_released_matrix`
  - `description=lincs_l1000_chempert_harmonizome_notebook_style`
  - `enabled=false`
- `HZ2`
  - `model_family=hz_released_matrix`
  - `description=lincs_l1000_crisprko_harmonizome_notebook_style`
  - `enabled=false`

### Less Recommended

Single-model option:

- `HZ1`
  - `model_family=hz_released_matrix`
  - `description=lincs_l1000_harmonizome_notebook_style`
  - requires `--hz_assay {chempert,crisprko}`

## Proposed Inputs

For `HZ1` chempert:

- `--expression_tsv inputs/LINCS_L1000/cp_mean_coeff_mat.tsv.gz`
- `--mapping_file HarmonizomePythonScripts/mappingFile_2017.txt`

For `HZ2` crisprko:

- `--expression_tsv inputs/LINCS_L1000/xpr_mean_coeff_mat.tsv.gz`
- `--mapping_file HarmonizomePythonScripts/mappingFile_2017.txt`

Shared:

- `--dig_dir`
- `--out_root`
- provenance mirror options

## Proposed Runtime Shape

Add dedicated all-dataset runners:

- `src/run_lincs_l1000_hz_chempert_model.py`
- `src/run_lincs_l1000_hz_crisprko_model.py`

or one shared runner:

- `src/run_lincs_l1000_hz_model.py`

with explicit branching by model ID.

Because these are matrix-level all-dataset workflows, the outer layout should look like:

- `outputs/genesets/all_signatures/models/HZ1/`
- `outputs/genesets/all_signatures/models/HZ2/`

Each model should write:

- `workflow/`
- `tissue_extractor/`
- `commands.md`
- `run.log`

This mirrors the MoTrPAC `HZ1` pattern, except the grouping key is:

- `all_signatures`

rather than:

- `all_tissues`

## Proposed Use Of `dig`

As with the revised MoTrPAC `HZ1` path, `dig` should be the authoritative GMT writer.

Recommended pattern:

1. run the notebook-replica logic through a pipeline wrapper
2. materialize a dig-compatible signed table
3. call a `dig` converter for authoritative GMT emission

There are two likely options:

### Option A: Reuse `signed_term_gene`

If the notebook-replica output can be transformed into a table like:

- `term`
- `gene_id`
- `gene_symbol`
- `score`
- `sign`

then the existing/recent `dig` converter added for MoTrPAC:

- `convert signed_term_gene`

is probably sufficient.

This is the preferred approach if it preserves the notebook output cleanly.

### Option B: Add A LINCS-specific `dig` converter

If chempert and crisprko need materially different ranking or sign handling from `signed_term_gene`, then add:

- `convert lincs_signed_matrix`

But do not do that unless reuse fails, because `signed_term_gene` is already the closest shared abstraction.

## Expected Workflow Inputs And Intermediate Tables

### Chempert

The standalone script currently:

- loads `cp_mean_coeff_mat.tsv.gz`
- transposes to `Gene x Chemical Perturbation`
- maps genes through the Harmonizome mapping file
- z-scores each gene across perturbations
- keeps rows with `abs(z) >= threshold`
- writes combined GMT terms:
  - `<perturbation>_Up`
  - `<perturbation>_Down`

Pipeline adaptation should therefore emit an intermediate signed table with:

- `term = chemical perturbation id`
- `gene_symbol`
- `score = abs(z)` or raw `z`, depending on converter contract
- `sign = +1 / -1`

### CRISPRKO

The standalone script currently:

- loads `xpr_mean_coeff_mat.tsv`
- removes `BRDN*` unmapped KO rows
- maps measured genes and KO genes through the mapping file
- transposes to `Gene x Gene KO`
- stacks long
- keeps top positive and top negative genes per KO
- writes combined GMT terms:
  - `<KO>_Up`
  - `<KO>_Down`

Pipeline adaptation should emit an intermediate signed table with:

- `term = KO gene`
- `gene_symbol`
- `score = effect size magnitude`
- `sign = +1 / -1`

## Proposed Output Layout

For each model:

- `workflow/`
  - notebook-style processed table
  - audit/summary TSV
  - any intermediate signed term-gene table passed into `dig`
- `tissue_extractor/`
  - `genesets.gmt`
  - `geneset.tsv`
  - `geneset.full.tsv`
  - `geneset.meta.json`
  - `geneset.provenance.json`
  - `signature_summary.tsv`
  - `run_manifest.json`

The authoritative GMT should be:

- `tissue_extractor/genesets.gmt`

## Required Companion Tracking Files

Because the implementation will adapt notebook-replica scripts, add companion notes like:

- `src/build_lincs_l1000_chempert_hz1.md`
- `src/build_lincs_l1000_crisprko_hz2.md`

Each should record:

- source script path
- copied or wrapped logic
- any intentional deviations

## Recommended Next Step

Before code edits, decide the model-ID policy:

### Recommended

- `HZ1` = chempert
- `HZ2` = crisprko

### Alternative

- `HZ1` only, with required `--hz_assay {chempert,crisprko}`

If you want me to proceed after review, I should implement the recommended two-model design unless you explicitly want the single-`HZ1` variant.
