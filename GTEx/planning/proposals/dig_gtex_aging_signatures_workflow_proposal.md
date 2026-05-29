# Implemented Direction: Notebook-Equivalent GTEx Aging-Signature Workflow In `dig-gene-set-extractors`

This note records the `dig-gene-set-extractors` workflow/converter additions needed so that `HZ1` can use notebook-equivalent GTEx aging-signature logic while producing outputs in standard `dig` workflow/converter format.

The goal is:

- preserve the biological logic of the notebook-style GTEx aging-signature workflow
- have the authoritative outputs follow `dig-gene-set-extractors` conventions rather than the standalone script's native file layout

## Goal

Support a `dig` workflow that reproduces the important behavior of:

- `build_gtex_aging_signatures_limma_voom_v10_lowmem.py`

including:

- broad tissue grouping
- notebook-style Ensembl-to-symbol mapping
- deterministic age-group balancing
- limma/voom DEA
- notebook-style signed GMT extraction

while writing outputs in `dig`'s usual style:

- workflow outputs
- `deg_long.tsv`
- extractor outputs
- `genesets.gmt`
- manifests
- provenance files

## Why This Is Needed

Current GTEx-local notebook-style logic and current `dig` logic differ in two major ways:

1. biological workflow behavior
2. output contract

If `HZ1` is to fit naturally into the rest of the GTEx model system and still use `dig` as the authoritative output layer, then the notebook-style biology needs to be implemented inside `dig`, not just wrapped outside it.

## Implemented Additions In `dig-gene-set-extractors`

### 1. New workflow: `gtex_aging_signatures`

Added workflow:

- `geneset_extractors.cli workflows gtex_aging_signatures`

Inputs should include:

- raw GTEx reads GCT
- sample attributes
- subject phenotypes
- `human_gene_info`
- tissue grouping mode
- tissue selection
- age groups to compare
- reference age group
- random seed
- minimum samples per group
- optional prefilter mode

Responsibilities:

- build GTEx sample metadata
- group by broad tissue
- construct age comparisons against `20-29`
- perform notebook-style deterministic balancing
- run limma/voom per comparison
- emit per-comparison DEA outputs and one combined `deg_long.tsv`

This would move the main notebook-style biology under `dig`.

### 2. `human_gene_info` Ensembl-to-symbol mapping mode

Add a mapping mode to the workflow so it can reproduce notebook-style gene handling.

Required behavior:

- use GCT `Name` as Ensembl ID
- strip version suffixes
- map Ensembl IDs to symbols using `human_gene_info`
- keep only mapped genes
- resolve duplicate Ensembl IDs by highest variance
- resolve duplicate symbols by highest variance

This is distinct from:

- GTF annotation mode
- existing symbol-passthrough behavior

So it should be an explicit mapping mode, not an implicit side effect.

### 3. Deterministic balanced comparison sampling

Add explicit support for notebook-style balancing:

- compare each target age group to `20-29`
- sample both groups down to the smaller group size
- use fixed `random_state=1`

This should be implemented as a first-class workflow option, not left to external wrappers.

### 4. Notebook-style limma/voom DEA path

The workflow should use explicit limma/voom behavior consistent with the notebook.

That means:

- build control/case matrices per comparison
- run limma/voom per comparison
- emit one result table per comparison
- emit a combined long-form DEA table

The combined table should be compatible with downstream `rna_deg_multi`-style extraction.

### 5. New GMT extraction mode in `convert rna_deg_multi`

Current generic GMT extraction behavior is not sufficient to match the notebook-style `top-per-direction` logic.

Added new GMT selection/extraction mode:

- `--gmt_mode top_per_direction`

and supporting options such as:

- `--gmt_top_n_per_direction`
- `--gmt_sort_by logFC_abs|P.Value|adj.P.Val|t`

Required behavior:

- split genes by sign of `logFC`
- sort each sign independently
- keep top N genes per direction

This matches the notebook-like GTEx aging-signature export logic much more closely than generic top-k selection.

### 6. Signed-set naming and output conventions

Allow the workflow/converter path to emit signatures in a way that fits the notebook semantics while still following `dig` output layout.

Recommended naming base:

- one comparison signature per tissue/age pair

For example:

- `GTEx_AdiposeTissue_20-29_vs_40-49`

Then the converter can emit signed sets under standard `dig` conventions.

### 7. Workflow outputs compatible with `dig`-style downstream handling

The workflow should write:

- workflow summary
- comparison manifest
- selected-sample audit
- `deg_long.tsv`
- provenance graph

This would let GTEx-local wrappers treat `HZ1` more like the other models.

## Recommended GTEx-Local Usage After `dig` Changes

With the new `dig` workflow in place, GTEx-local `HZ1` becomes a thin wrapper:

- choose broad tissue
- choose notebook-faithful parameters
- call `workflows gtex_aging_signatures`
- call the corresponding converter with notebook-style GMT mode

Then `HZ1` would naturally write into the existing GTEx-style model tree, for example:

- `outputs/genesets/<broad_tissue>/models/HZ1/workflow/`
- `outputs/genesets/<broad_tissue>/models/HZ1/extractor/`

This is a much cleaner fit than maintaining GTEx-local notebook-specific GMT generation as the authoritative path.

## Proposed `HZ1` Parameter Profile

Once supported by `dig`, `HZ1` would likely fix:

- tissue grouping: `broad`
- mapping mode: `human_gene_info`
- reference age: `20-29`
- comparison ages:
  - `30-39`
  - `40-49`
  - `50-59`
  - `60-69`
  - `70-79`
- random state: `1`
- prefilter mode:
  - `none` for the current target command
- GMT mode:
  - `top_per_direction`
- top N per direction:
  - `250`
- sort by:
  - `logFC_abs`

That would encode the notebook-style behavior declaratively.

## Expected Tradeoff

This approach changes the target from:

- exact reproduction of the standalone script's file layout

to:

- notebook-equivalent biology
- `dig`-style outputs

That is usually the better fit if the long-term goal is consistency with the rest of the GTEx/dig model ecosystem.

## Validation Requirement

Because the output contract would change to `dig` style, validation should focus on biological equivalence rather than file-by-file identity.

Recommended comparisons:

- per-comparison DEG tables
- up/down gene membership overlap
- top-250 per-direction gene sets
- tissue-by-comparison signature sizes

The `dig`-based workflow should only replace the standalone script for `HZ1` after those comparisons are satisfactory.

## Current Status

The GTEx-side `HZ1` path now targets the `dig` workflow/converter design described here:

- a new GTEx aging-signature workflow
- `human_gene_info` mapping mode
- deterministic balanced age-comparison sampling
- notebook-style limma/voom DEA path
- notebook-style `top_per_direction` GMT extraction mode

GTEx-local code can now keep `HZ1` as a thin wrapper and let `dig` own both the biology and the output structure.
