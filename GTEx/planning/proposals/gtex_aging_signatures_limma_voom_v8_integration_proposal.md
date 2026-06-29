# Historical Proposal: Integrating `build_gtex_aging_signatures_limma_voom_v10_lowmem.py`

This note captures an earlier integration direction for:

- `geneset-extractor-dev/GTEx/planning/build_gtex_aging_signatures_limma_voom_v10_lowmem.py`

into the GTEx codebase while preserving the exact output produced by the current command:

```bash
python build_gtex_aging_signatures_limma_voom_v10_lowmem.py \
  --expression-gct GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz \
  --sample-attributes GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt \
  --subject-phenotypes GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt \
  --human-gene-info human_gene_info \
  --output-dir downloads_gtex_aging \
  --filter-mode none \
  --gmt-mode top-per-direction \
  --top-n 250 \
  --gmt-sort-by logFC_abs \
  --chunksize 1000
```

This updated proposal assumes the integration should **not** rely on Ma'ayan Lab limma-voom helper functions at runtime.

## Status

This proposal has effectively been superseded by the `dig`-based `HZ1` direction documented in:

- [dig_gtex_aging_signatures_workflow_proposal.md](/home/ryank/software/geneset_extractors/geneset-extractor-dev/GTEx/planning/proposals/dig_gtex_aging_signatures_workflow_proposal.md)

The active implementation direction is now:

- notebook-faithful biology inside `dig-gene-set-extractors`
- GTEx-local `HZ1` as a thin wrapper around the new `dig` workflow and converter

## Recommendation

Integrate this as a new, separate GTEx model family rather than as a variant of:

- `AB*`
- `AC*`
- `HZ*`

Suggested family/model ID:

- `AS1`

Suggested family name:

- `aging_signature_notebook`

## Why This Should Be Separate

The script is not just another parameterization of the current GTEx build pipeline.

It has a distinct workflow:

- uses GTEx V8 raw reads
- uses broad `SMTS` tissues across the whole dataset
- uses notebook-specific sample balancing with `random_state=1`
- uses notebook-specific Ensembl-to-symbol mapping from `human_gene_info`
- uses Ma'ayan Lab limma-voom helper functions
- writes its own combined GMT outputs

The current `build_genesets.sh` pipeline instead assumes:

- tissue-oriented prepared bundles
- model runners that emit per-model/per-tissue outputs
- optional use of `dig-gene-set-extractors` for gene-set conversion

Trying to force this script into the `AB`/`AC`/`HZ` build path would add special cases and increase the chance of output drift.

## Exact-Output Requirement

The goal is to ensure the integrated version produces exactly the same output as the current standalone script and command.

That means the primary output path must continue to use the existing script logic for:

- sample metadata construction
- Ensembl-to-symbol mapping
- balanced age-comparison sampling
- limma-voom helper execution
- per-comparison result TSVs
- GMT writing

In particular, for the current command the exact output behavior depends on:

- `--filter-mode none`
- `--gmt-mode top-per-direction`
- `--top-n 250`
- `--gmt-sort-by logFC_abs`
- `--chunksize 1000`

Those settings should remain the authoritative output path.

However, because this proposal now removes the Ma'ayan Lab limma-voom helper dependency, exact output should be treated as something to verify empirically against the current script rather than assumed automatically.

## Where `dig-gene-set-extractors` Can Be Used

`dig-gene-set-extractors` should not replace the authoritative GMT-writing path for this model.

It can be used only as an optional secondary export path, for example:

- to convert the per-comparison limma-voom TSVs into secondary `dig`-style outputs
- to generate additional provenance-like JSON artifacts
- to generate alternate converter GMTs for side-by-side comparison

If added, those outputs should be written into a separate subdirectory such as:

- `dig_secondary/`

and should not replace:

- `gene_set_library_up.gmt`
- `gene_set_library_dn.gmt`

## Replace Ma'ayan Lab Runtime Helpers With GTEx-Local Code

The integrated runtime path should not depend on:

- `maayanlab_bioinformatics.normalization.filter.filter_by_expr`
- `maayanlab_bioinformatics.dge.limma_voom_differential_expression`
- `maayanlab_bioinformatics.dge.limma_voom.up_down_from_limma_voom`

Instead:

### `filter_by_expr`

- when `--filter-mode none`, preserve the current no-prefilter behavior exactly
- when tissue filtering is desired later, call `edgeR::filterByExpr` directly from GTEx-local R code

### limma-voom differential expression

Replace the helper with explicit GTEx-local R code using:

- `edgeR`
- `limma`
- `voom`
- `lmFit`
- `eBayes`
- `topTable`

The GTEx-local runtime script should generate and run the needed R code directly, just as other GTEx-local workflows already do.

### GMT extraction

For the current command, the primary GMT path should stay GTEx-local:

- `--gmt-mode top-per-direction`
- `--top-n 250`
- `--gmt-sort-by logFC_abs`

So the integrated runtime should continue to use the script's own GMT-writing logic for the authoritative outputs.

In particular, it should preserve:

- `write_gmt_top_per_direction_from_limma_results()`

and should not replace that path with generic `dig` GMT generation for the primary outputs.

## Proposed Integration Shape

### Runtime entrypoint

Move or copy the current planning script into the runtime tree, for example:

- `geneset-extractor-dev/GTEx/src/run_gtex_aging_signatures_limma_voom_v8.py`

The runtime version should preserve the current analysis logic unchanged except for:

- path cleanup
- log file handling
- command provenance writing
- output-root conventions
- replacing Ma'ayan helper calls with GTEx-local R/utility code
- optional secondary `dig` export hooks

### Shell wrapper

Add:

- `geneset-extractor-dev/GTEx/run/run_gtex_aging_signatures_limma_voom_v8.sh`

This wrapper should expose the runtime script directly and keep the CLI explicit.

### GTEx-local DEA implementation

The new runtime script should:

- keep the same sample balancing logic
- keep the same Ensembl-to-symbol mapping logic
- keep the same per-comparison TSV schema
- replace only the limma-voom execution layer with GTEx-local R code

This keeps the surface behavior notebook-faithful while removing the external helper dependency.

### Planning/model registration

Do not force this into the regular `model_list.tsv` used by `build_genesets.sh`.

Instead add a separate planning file, for example:

- `geneset-extractor-dev/GTEx/planning/aging_signature_model_list.tsv`

with a row such as:

- `AS1`
- `family=aging_signature_notebook`
- description of the fixed notebook-faithful limma-voom aging-signature build

This keeps the model documented without implying it is runnable through the normal `AB`/`AC` path.

## Proposed Output Location

Write outputs alongside existing GTEx outputs but in a dedicated subtree, for example:

- `geneset-extractor-dev/GTEx/outputs/aging_signatures/AS1/`

Suggested contents:

- `limma_voom_results/`
- `filtered_counts/` if enabled
- `gene_set_library_up.gmt`
- `gene_set_library_dn.gmt`
- `gene_attribute_matrix_limma_t.tsv.gz`
- `attribute_metadata.tsv`
- `gtex_aging_processing_audit.tsv`
- `gtex_aging_sample_metadata.tsv`
- `run_manifest.json`
- `commands.md`
- `run.log`

This keeps the outputs adjacent to the existing GTEx outputs without pretending they are normal per-tissue model directories.

## Best-Fit Classification

The best fit is:

- a new individual model family
- a dedicated runtime entrypoint
- dedicated output subtree

not:

- a new `AB*` model
- a new `AC*` model
- a special case inside `build_genesets.sh`

## Minimal Implementation Plan

1. Copy the script into `GTEx/src/` as the runtime entrypoint.
2. Replace Ma'ayan helper calls with GTEx-local R and Python utility code.
3. Preserve the current defaults needed to match the existing command.
4. Add a shell wrapper in `GTEx/run/`.
5. Add `commands.md`, `run.log`, and manifest handling if needed.
6. Optionally add a disabled-by-default `dig_secondary/` export step.

## Validation Requirement

Because the runtime DEA implementation would no longer call the original Ma'ayan helper, the integration should include an explicit validation step:

- run the current standalone planning script with the reference command
- run the integrated runtime script with the equivalent settings
- compare:
  - per-comparison limma result TSVs
  - `gene_set_library_up.gmt`
  - `gene_set_library_dn.gmt`

The integrated runtime should only be treated as notebook-equivalent after those comparisons pass to an acceptable tolerance or exact match standard.

## Summary

The integration that makes the most sense is:

- new standalone GTEx model family
- dedicated entrypoint
- primary outputs produced by notebook-faithful GTEx-local logic
- optional `dig` outputs only as secondary artifacts

This is the cleanest way to integrate the script into the repo while preserving exact output.
