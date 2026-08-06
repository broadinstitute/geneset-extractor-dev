# Add a New Library

For the additive new-library submission contract, see
[`docs/submissions/README.md`](../../submissions/README.md). It supplements
this workflow and does not change requirements for existing libraries.
Start with the source proposal and paired-PR sequence in
[`docs/submissions/contributor-workflow.md`](../../submissions/contributor-workflow.md).

This guide describes how to add a new library to:

- `geneset-extractor-dev`
- `dig-gene-set-extractors`

The target standard is the one established by the GTEx, MoTrPAC, HuBMAP, and LINCS_L1000 libraries on this branch.

The most important requirements are:

- `geneset-extractor-dev` must act as a wrapper around workflow logic implemented in `dig-gene-set-extractors`
- library structure, configs, scripts, and outputs must match existing patterns as closely as possible
- outputs must support model sidecars, metadata refresh, provenance refresh, and S3 publishing without special-case logic
- new code should reuse existing conventions instead of inventing new ones

## Roadmap

At a high level, the work should proceed like this:

1. clone both repositories and branch from `main`
2. inspect the new library data and determine its natural model and partition structure
3. study GTEx, MoTrPAC, HuBMAP, and LINCS_L1000 to identify the closest existing pattern
4. implement primary workflow logic in `dig-gene-set-extractors`
5. implement wrapper/config/run orchestration in `geneset-extractor-dev`
6. verify that metadata, provenance, model sidecars, refresh, and publish flows all work without special cases
7. package the run scripts and outputs and upload them to the submissions directory

## 1. Clone Repositories

Clone both repositories side by side:

```bash
git clone git@github.com:broadinstitute/geneset-extractor-dev.git
git clone git@github.com:flannick/dig-gene-set-extractors.git
```

Recommended parent directory layout:

```text
workspace/
  geneset-extractor-dev/
  dig-gene-set-extractors/
```

## 2. Branch From `main`

Start from `main` in each repo and create a unique branch name in both repositories.

Example branch names:

- `yourinitials-add-libraryname`
- `yourname-add-libraryx-20260627`

Commands:

```bash
git -C geneset-extractor-dev checkout main
git -C geneset-extractor-dev pull --ff-only
git -C geneset-extractor-dev checkout -b yourname-add-libraryx-20260627

git -C dig-gene-set-extractors checkout main
git -C dig-gene-set-extractors pull --ff-only
git -C dig-gene-set-extractors checkout -b yourname-add-libraryx-20260627
```

Use the same branch name in both repos unless there is a strong reason not to.

## 3. Acquire Library Data

Before writing code, acquire and inspect the new library inputs.

At minimum, identify:

- raw input files needed to run the workflow from scratch
- file formats
- organism and genome build
- whether there are natural tissues, assays, perturbation groups, or other partitions
- whether the data supports one model or multiple models
- whether any existing DIG workflow family already matches the assay

Downloaded data should live outside committed source trees. If you keep local downloaded inputs in this workspace, use the same pattern already used here:

```text
inputs/LIBRARY_NAME/
```

Do not hard-code local machine paths into committed code.

## 4. Use an AI Coding Agent

Use an AI coding agent of your choosing. Give it the repo context, the new library data description, and the standards below.

The agent should help with:

- porting workflow logic into `dig-gene-set-extractors`
- creating wrapper/config/run structure in `geneset-extractor-dev`
- aligning outputs with existing metadata/provenance standards
- avoiding regressions in existing libraries

Provide the agent with:

- `geneset-extractor-dev/docs/dev/add_new_library/AGENTS.md`
- this document
- examples from GTEx, MoTrPAC, HuBMAP, and LINCS_L1000

### Full repo-context prompt

Use a prompt like this early in the project so the agent understands how the two repos work together and what methods already exist:

```text
I am adding a new library called LIBRARY_X across two repositories:

1. geneset-extractor-dev
This repo is the wrapper/orchestration layer. It should contain:
- library-specific config TSVs such as model_list.tsv, model_manifest.tsv, model_description_templates.tsv, and partition lists
- thin Python wrapper scripts under LIBRARY_X/src
- cluster and Apptainer run scripts under geneset-extractor-dev/run
- worklist generation, model selection, and refresh/publish integration

2. dig-gene-set-extractors
This repo is the primary workflow-logic layer. It should contain:
- workflow implementations
- converter logic
- provenance graph generation
- reusable assay logic that should not be duplicated in geneset-extractor-dev

The new library must follow the same standards already established by four existing libraries:

- GTEx
  Uses multiple model families over tissue-partitioned bulk RNA-seq inputs. The wrapper builds tissue/model worklists and DIG owns the workflows for age-binned, continuous-age, and related gene-set extraction methods.

- MoTrPAC
  Uses multiple model families over tissue-partitioned transcriptomics data. Some models run directly from raw-count-derived contrasts, while others build aggregated libraries from either released differential analysis inputs or raw-input-derived intermediate results.

- HuBMAP
  Uses library-generation workflows over released ASCT+B inputs. DIG performs the workflow logic and provenance generation, while the wrapper selects models, handles cluster execution, and refreshes metadata/provenance/model sidecars.

- LINCS_L1000
  Uses multiple library-generation models for different signature sources, such as chemical perturbation and CRISPR knockout. DIG owns the workflows and converters; the wrapper handles model selection, manifests, and cluster integration.

Rules you must follow:
- keep geneset-extractor-dev as a wrapper around DIG
- place primary workflow logic in dig-gene-set-extractors
- match the existing directory structure, config style, naming, metadata, provenance, model sidecars, and publish/refresh behavior
- avoid inventing new structures when an existing pattern can be reused
- compare any new design explicitly against GTEx, MoTrPAC, HuBMAP, and LINCS_L1000

Please start by inspecting the four existing libraries in both repos and propose:
- the closest existing pattern to copy
- the likely model families for LIBRARY_X
- the partition list(s) needed
- the minimum file set required in each repo
- any expected deviations from existing standards
```

### Example prompts

Prompt 1:

```text
I want to add a new library called LIBRARY_X to geneset-extractor-dev and dig-gene-set-extractors. Follow the standards used by GTEx, MoTrPAC, HuBMAP, and LINCS_L1000. geneset-extractor-dev must remain a wrapper to dig-gene-set-extractors. First inspect the existing library patterns and propose the minimum file set and config structure needed.
```

Prompt 2:

```text
Implement the DIG-side workflow logic for LIBRARY_X by following the closest existing assay pattern in dig-gene-set-extractors. Do not add special-case output handling. The final outputs must support metadata refresh, provenance refresh, model sidecars, and publishing using the existing shared tooling.
```

Prompt 3:

```text
Now implement the geneset-extractor-dev wrapper side for LIBRARY_X. Create config files, wrapper scripts, and cluster/apptainer run scripts that follow the GTEx, MoTrPAC, HuBMAP, and LINCS_L1000 patterns as closely as possible.
```

Prompt 4:

```text
Compare the proposed LIBRARY_X output layout against GTEx, MoTrPAC, HuBMAP, and LINCS_L1000. Identify any deviations from existing metadata, provenance, model.json, extractor directory, manifest, or publish/refresh standards and fix them.
```

## 5. Design Rule: DIG Owns Workflow Logic

Put the primary workflow logic in `dig-gene-set-extractors`.

`geneset-extractor-dev` should only provide:

- library-specific configs
- wrapper scripts
- model orchestration
- cluster submission
- Apptainer invocation
- refresh/publish integration

Avoid pushing core assay logic into `geneset-extractor-dev` unless it is strictly wrapper-specific.

Good pattern:

- DIG implements the workflow and converter behavior
- `geneset-extractor-dev` calls stable DIG CLI commands or thin wrapper scripts

Bad pattern:

- `geneset-extractor-dev` duplicates workflow logic that should live in DIG
- the library only works through ad hoc generated scripts or one-off notebooks

## 6. Mirror Existing Library Structure

Create a top-level library directory in `geneset-extractor-dev`:

```text
geneset-extractor-dev/LIBRARY_X/
  config/
  run/
  src/
  planning/            # optional but recommended
```

### `config/`

Follow existing library patterns. Typical files include:

- `model_list.tsv`
- `model_manifest.tsv`
- `model_description_templates.tsv`
- a library-specific partition list such as:
  - `tissue_list.tsv`
  - `signature_list.tsv`
  - `dataset_list.tsv`

Use headers. Keep fields explicit and machine-readable.

At minimum, config files should support:

- enabled/disabled models
- model family/group mapping
- model-specific parameters
- input partitions if applicable
- description templates for refresh tooling

### `run/`

Add wrapper scripts that follow existing naming conventions.

Examples to emulate:

- `submit_gtex_models_cluster_apptainer.sh`
- `submit_motrpac_models_cluster_apptainer.sh`
- `submit_lincs_l1000_models_cluster_apptainer.sh`
- `submit_hubmap_models_cluster_apptainer.sh`

If the new library supports cluster operation, add both:

- cluster wrapper
- cluster + Apptainer wrapper

If model JSON generation is needed independently, also follow the existing `write_*_model_json_apptainer.sh` pattern.

### `src/`

Add only thin wrapper logic here.

Examples:

- build worklists
- dispatch model families
- translate config rows into DIG CLI calls
- write `geneset.model.json` sidecars if needed

## 7. Model Structure

New libraries may have one model or multiple models depending on the input data and analytical choices.

The model structure should follow the same style already used here:

- GTEx: multiple model families for related biological questions
- MoTrPAC: multiple model families reflecting distinct analytical approaches
- HuBMAP: multiple models for different library-generation paths
- LINCS_L1000: multiple models for different signature sources

When adding a new library, decide whether it has:

- a single model family
- multiple model families
- multiple variants within a family
- optional input partitions such as tissue, assay, signature type, or dataset

### Modeling rules

- define models in config, not in hard-coded shell conditionals alone
- use stable model IDs
- map model IDs to model families/groups
- record model-specific parameters in config or manifest TSVs
- ensure each model can produce a valid `geneset.model.json`
- ensure refresh tooling can patch metadata descriptions per model

If the library naturally supports multiple analytical styles, model them explicitly instead of burying differences in undocumented flags.

### Existing modeling patterns to reuse

When deciding how many models to create, prefer one of the patterns already used in the current libraries:

- GTEx-style:
  tissue-partitioned models with multiple analytical families over the same assay
- MoTrPAC-style:
  tissue-partitioned models with both direct differential-expression workflows and aggregated library workflows
- HuBMAP-style:
  one or a small number of library-construction paths over a released reference resource
- LINCS_L1000-style:
  multiple signature-source models over a shared general output contract

The goal is not to invent a fifth structure if one of these four already matches the new library.

## 8. Output Standard

Outputs must follow the same standards already used across the existing libraries.

The final user-facing outputs must fit the shared tooling for:

- metadata patching
- provenance rewriting
- model-sidecar generation
- S3 publishing

### Required output conventions

- final extractor directory should be named `extractor`
- metadata file should be `geneset.meta.json`
- provenance file should be `geneset.provenance.json`
- model sidecar should be `geneset.model.json`
- intermediate workflow outputs should be under `workflow/`
- final gene sets should be emitted in the same style as existing libraries when the assay supports it

Do not invent a library-specific final output structure if the standard one can be reused.

### Directory style

```text
<out_root>/genesets/<partition>/models/<model_id>/
  workflow/
  extractor/
```

If the library does not naturally partition by tissue, choose the nearest equivalent partition label and still keep the same top-level output contract.

## 9. Validate Shared Tooling

Before considering the work complete, confirm that the new library works with the existing shared utilities:

- model JSON writing
- metadata refresh
- provenance refresh
- publish to S3
- path rewriting and source mapping if needed

The preferred standard is that the new library works with the current shared tooling without introducing library-specific exceptions.

## 10. Package Submission Artifacts

At the end of the workflow, package the deliverables for review.

Collect:

- all run scripts used for the new library
- any wrapper scripts needed to reproduce the run
- the resulting output directory or validated test-run output directory

Create one or more zip archives and upload them to:

```text
/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions
```

The submission archive should make it easy for a reviewer to inspect:

- the commands used to run the library
- the exact run scripts
- the output structure
- the metadata/provenance/model sidecar results

Match existing libraries as closely as possible. In practice this usually means:

```text
<out_root>/genesets/<partition>/models/<model_id>/
  workflow/
  extractor/
```

For libraries with no natural tissue or partition dimension, use an existing all-library convention such as:

```text
genesets/all_signatures/models/<model_id>/
```

## 9. Metadata and Provenance Requirements

The new library must work with existing shared tools:

- `run/patch_metadata.sh`
- `run/refresh_model_metadata_and_provenance.sh`
- `run/publish_library_to_s3.sh`

That means:

- final metadata must contain enough information to rebuild provenance
- upstream workflow provenance graphs should be connected correctly
- model-specific variables should be available for templated descriptions
- S3 URI rewriting should work without library-specific hacks

The library should not require a separate bespoke metadata or provenance pathway.

## 10. Publishing Requirements

The outputs must publish cleanly through the existing library publishing flow.

This means:

- final outputs belong under the standard output root
- provenance must identify the true external input files needed for reruns
- local filesystem paths must be rewritable during refresh/publish
- no hidden dependency on unpublished local intermediate paths

## 11. Preferred Development Process

Recommended order:

1. inspect data and define candidate model structure
2. implement or adapt DIG workflow logic
3. add minimal tests or smoke checks in DIG where practical
4. add `geneset-extractor-dev` configs
5. add wrapper scripts
6. add cluster/apptainer scripts
7. run a small local or single-task test
8. verify output structure
9. verify metadata/provenance refresh
10. verify publishing compatibility

## 12. Review Checklist

Before calling the library complete, verify:

- DIG contains the workflow logic
- `geneset-extractor-dev` acts only as wrapper/orchestration
- config files are present and headered
- model list and manifest follow existing conventions
- model descriptions can be patched through shared refresh tooling
- outputs land in the standard layout
- final output uses `extractor/`
- metadata, provenance, and model sidecar files are present
- no library-specific exceptions were added to shared publish/refresh code unless unavoidable
- any new shared-code changes do not regress GTEx, MoTrPAC, HuBMAP, or LINCS_L1000

## 13. What to Reuse First

When in doubt, copy the closest existing pattern:

- GTEx for tissue + model arrays and rich model families
- MoTrPAC for multi-family assay workflows with shared tooling
- HuBMAP for library-style outputs with shared refresh/publish expectations
- LINCS_L1000 for all-signatures style outputs and simple model families

The goal is not novelty. The goal is consistency with the existing branch.
