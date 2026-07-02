# Publishable Library Attributes

This document summarizes the attributes shared by the four existing publishable libraries in this branch:

- `GTEx`
- `HuBMAP`
- `LINCS_L1000`
- `MoTrPAC`

Reference outputs under `./submissions/reference/ryank` are treated as publishable examples. A newly added library should match these standards closely if its outputs are expected to be considered publishable.

## Purpose

Use this as:

- a review checklist for collaborators adding a new library
- a definition of the minimum shared contract for wrapper code, configs, and outputs
- a way to decide whether a new library fits the current branch standards without special-case handling

## Shared Codebase Attributes

### Two-repo division of responsibility

All publishable libraries follow the same split:

- `dig-gene-set-extractors` owns the primary workflow logic
- `geneset-extractor-dev` owns wrapper logic, config, orchestration, submission, refresh, and publishing

In practice this means:

- assay-specific workflows live in DIG
- conversion to final gene sets lives in DIG
- provenance graph generation lives in DIG
- library-specific wrapper scripts live in `geneset-extractor-dev`
- cluster and Apptainer submit scripts live in `geneset-extractor-dev`

If a new library requires most of its logic to live in `geneset-extractor-dev`, it is not following the current standard.

### Config-driven models

All four libraries define model behavior through config files rather than hard-coded ad hoc shell logic.

Expected config files:

- `config/model_list.tsv`
- `config/model_manifest.tsv`
- `config/model_description_templates.tsv`

Expected partition/config lists where applicable:

- `tissue_list.tsv`
- `broad_tissue_list.tsv`
- or an equivalent explicit partition list with a header row

Shared properties:

- stable model IDs
- explicit enabled/disabled state
- model-family grouping
- explicit parameterization in manifest TSVs
- user-facing descriptions stored separately from code

### Standard library directory layout

Each library follows the same top-level wrapper structure:

```text
LIBRARY/
  config/
  run/
  src/
```

Optional planning or helper directories are acceptable, but the main wrapper pattern should stay the same.

### Standard run-script behavior

All four libraries expose comparable run/submit patterns:

- local wrapper scripts
- cluster submit scripts
- Apptainer-backed cluster submit scripts
- config-driven worklist generation
- array-task execution
- optional model filtering
- optional partition filtering where relevant
- refresh functionality for metadata and provenance

Shared behavioral expectations:

- they can run outside repo root when pointed to the repo script
- output roots are explicit
- worklists are explicit TSV files
- submit scripts do not require users to manually edit code

### Model-sidecar support

All publishable libraries now support `geneset.model.json` sidecars.

These are used for:

- templated metadata descriptions
- provenance refresh
- GMT description generation
- model-specific interpretation of outputs

A new library should write model sidecars in the same output tree as the extractor outputs and should support regenerating them during refresh flows.

### Shared refresh/publish integration

A publishable library is expected to work with the shared tools without one-off exceptions:

- metadata patching
- provenance rewrite/refresh
- model-sidecar regeneration
- GMT description rewrite during refresh
- output publishing to S3

If a new library needs custom manual repair after every run, it does not meet the current standard.

## Shared Output Attributes

### Output root structure

All publishable outputs follow a common structure under a run root:

```text
<run_root>/<library>_all_models/
  genesets/
```

Within `genesets/`, outputs are partitioned by the natural library scope:

- GTEx: tissue-partitioned
- MoTrPAC: tissue-partitioned plus `all_tissues` for aggregated models
- HuBMAP: `all_signatures`
- LINCS_L1000: `all_signatures`

Within each partition, model outputs live under:

```text
genesets/<partition>/models/<model_id>/
```

### Standard model output subdirectories

Each model directory is expected to contain:

- `workflow/`
- `extractor/`

Additional summaries or command logs are fine, but `workflow/` and `extractor/` are part of the shared contract.

### Standard final output files

The final publishable extractor output is expected to include, as applicable:

- `genesets.gmt`
- `geneset.meta.json`
- `geneset.provenance.json`
- `geneset.model.json`

Common additional files include:

- `geneset.full.tsv`
- `manifest.tsv` for grouped outputs
- `commands.md`
- `run.log`
- summary TSV files

Grouped models may also contain per-comparison subdirectories under `extractor/`.

### Metadata expectations

Publishable metadata should:

- describe the library and model clearly
- reflect the actual model-specific configuration
- support template-driven regeneration
- remain consistent with the corresponding provenance

Descriptions should be:

- library-specific
- model-specific
- partition-aware where applicable
- comparison-aware where applicable

### Provenance expectations

Publishable provenance should:

- begin from the true initial workflow inputs, not only later intermediate files
- preserve the workflow-to-extractor chain
- be refreshable without rerunning the full analysis
- support path rewriting for distributed or published contexts
- avoid broken graph connectivity between workflow outputs and downstream inputs

When refreshed for publication, provenance should also support:

- path sanitization
- replacement of local paths with publishable URIs or generic placeholders where required
- preservation of original files via `.orig` snapshots

### GMT expectations

Publishable GMT outputs should:

- use stable, model-appropriate gene set names
- follow branch naming conventions for the library
- have a populated second-column description
- distinguish signed outputs where applicable

Current branch standard:

- GMT descriptions are derived from model description templates plus row-specific context
- original GMT files are preserved as `.orig` during refresh
- refreshed GMT descriptions should be reproducible from model sidecars and templates

### Publishability expectations

A library is closer to publishable when:

- outputs can be packaged without manual editing
- metadata and provenance can be refreshed after the run
- model sidecars can be regenerated
- GMT descriptions can be regenerated
- publishing can target either all outputs or a filtered set of model IDs
- output trees do not depend on hidden local environment state

## Shared Review Criteria For A New Library

Collaborators adding a new library should be able to answer yes to all of the following.

### Codebase review

- Does DIG own the primary workflow logic?
- Does `geneset-extractor-dev` act mainly as a wrapper?
- Are model definitions config-driven?
- Are model IDs stable and explicit?
- Are partition lists explicit and headered?
- Are run scripts consistent with the other four libraries?
- Does the library support refresh and publish flows without manual repair?

### Output review

- Does the output tree follow `genesets/<partition>/models/<model_id>/`?
- Does each model have `workflow/` and `extractor/` directories?
- Are `geneset.meta.json`, `geneset.provenance.json`, and `geneset.model.json` present where expected?
- Do provenance files start from the real initial inputs?
- Are GMT names consistent and stable?
- Are GMT descriptions populated and model-specific?
- Can outputs be archived and shared without local-path cleanup by hand?

## Warning Signs That A New Library Is Not Yet Publishable

- core workflow logic exists only in `geneset-extractor-dev`
- model behavior is encoded mostly in shell conditionals rather than config
- output layout differs substantially from the four existing libraries
- metadata and provenance must be edited manually after every run
- provenance begins from intermediate files rather than true inputs
- GMT second-column descriptions are empty or generic
- publishing requires library-specific one-off code paths
- model sidecars are missing or incomplete

## Practical Standard

A good final test is:

- can the new library be run with the same style of submit scripts as the existing four
- can its metadata, provenance, and GMT descriptions be refreshed with the shared refresh flow
- can its outputs be filtered and published with the shared publish flow
- does its archived output look structurally similar to the reference outputs under `./submissions/reference/ryank`

If not, the library probably still needs adaptation before its output should be treated as publishable.
