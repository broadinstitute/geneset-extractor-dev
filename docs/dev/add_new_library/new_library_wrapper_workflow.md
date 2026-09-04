# New Library Wrapper Workflow

This document describes the expected end-to-end workflow for a new user adding a library to this branch standard.

It focuses on:

- which wrapper commands should exist
- when those commands should be run
- when outputs become publishable

This is the operational companion to:

- [add_new_library_workflow.md](/home/ryank/software/geneset_extractors/geneset-extractor-dev/docs/dev/add_new_library/add_new_library_workflow.md)
- [publishable_library_attributes.md](/home/ryank/software/geneset_extractors/geneset-extractor-dev/docs/dev/add_new_library/publishable_library_attributes.md)

## Core Principle

A new library should follow the same two-repo contract as the existing publishable libraries:

- `dig-gene-set-extractors` owns the primary workflow logic
- `geneset-extractor-dev` owns wrapper logic, config, orchestration, refresh, and publishing

The wrapper layer should expose a standard lifecycle:

1. define models and partitions in config
2. optionally write model sidecars
3. submit model runs
4. refresh metadata and provenance
5. optionally publish outputs

## Required Wrapper Command Types

Every new library should add wrapper commands comparable to the existing ones.

At minimum, a new library should provide one canonical local builder and, when
cluster execution is declared, the shared-launcher adapter below. Do not add
the obsolete library-local `run/submit_models.sh` scaffold.

### 1. Canonical local builder

```text
<Library>/run/build_<library>_genesets.sh
```

It must dispatch a single task from `config/task_manifest.tsv`, honor
`SUBMISSION_WORK_DIR`, and be the same execution path used by smoke, full, and
cluster runs.

### 2. Cluster submit wrapper

Preferred pattern:

```text
geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh
```

Optional non-Apptainer companion:

```text
geneset-extractor-dev/run/submit_<library>_models_cluster.sh
```

Purpose:

- generate a worklist from config
- submit array jobs
- run model tasks outside repo root
- support model filtering
- support partition filtering where relevant
- support model-sidecar-only and refresh-only modes

The Apptainer-backed submit script is the main standard because it is the most reproducible cluster entrypoint.

### 3. Model-sidecar writer

Preferred pattern:

```text
geneset-extractor-dev/run/write_<library>_model_json_apptainer.sh
```

Purpose:

- write or rewrite `geneset.model.json`
- support targeted runs for one model or one partition
- support sidecar generation before or after full workflow runs

In practice, this is optional if the submit script can already do:

- `--submit --write_model_only`

That is the better long-term pattern.

### 4. Refresh wrapper

Shared wrappers already exist:

- [refresh_model_metadata_and_provenance.sh](/home/ryank/software/geneset_extractors/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh)
- [refresh_model_metadata_and_provenance_apptainer.sh](/home/ryank/software/geneset_extractors/geneset-extractor-dev/run/refresh_model_metadata_and_provenance_apptainer.sh)

New library submit scripts should integrate with these by supporting:

- `--refresh_metadata_and_provenance`

Purpose:

- patch metadata descriptions from templates
- regenerate model sidecars if needed
- rewrite provenance
- rewrite GMT descriptions
- preserve originals as `.orig`
- optionally rewrite local paths to publish-safe locations

### 5. Publish wrapper

Shared wrapper:

- [publish_library_to_s3.sh](/home/ryank/software/geneset_extractors/geneset-extractor-dev/run/publish_library_to_s3.sh)

Purpose:

- publish already-refreshed output trees
- upload filtered subsets if needed

Publishing should not be the step that makes outputs publishable. Publishing should happen after outputs are already in publishable form.

## Expected User Workflow

The expected user workflow for a new library is below.

## Stage 1: Define Library Structure

Before any wrapper command is run, the library should already have:

- `LIBRARY/config/model_list.tsv`
- `LIBRARY/config/model_manifest.tsv`
- `LIBRARY/config/task_manifest.tsv`
- `LIBRARY/config/model_description_templates.tsv`
- one or more explicit partition list files where relevant

Examples of partitions:

- tissue
- study
- dataset
- signature collection
- all-signatures singleton partition

The submit wrapper should build its worklist from these files rather than from hard-coded shell logic.

## Stage 2: Optionally Write Model Sidecars First

This stage is useful during development and validation.

Preferred command pattern:

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --write_model_only
```

Typical filtered examples:

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --write_model_only \
  --model_id MODEL1
```

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --write_model_only \
  --partition_id PARTITION1
```

Expected result:

- `geneset.model.json` files are written or refreshed
- no main workflow outputs are required yet

This stage does **not** produce publishable output.

## Stage 3: Submit the Main Workflow Runs

This is the primary wrapper entrypoint.

Preferred command pattern:

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit
```

Filtered examples:

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --model_id MODEL1
```

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --model_id MODEL1,MODEL2
```

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --partition_id PARTITION1
```

Expected result:

- worklist TSV is generated
- array jobs are submitted
- outputs are produced under:

```text
<run_root>/<library>_all_models/genesets/<partition>/models/<model_id>/
```

Each completed model should produce:

- `workflow/`
- `extractor/`

and final extractor outputs such as:

- `genesets.gmt`
- `geneset.meta.json`
- `geneset.provenance.legacy.json`
- `geneset.provenance.dapper.yaml`
- `geneset.model.json`

At this point, outputs are **run-complete**, but they are not yet assumed publishable.

## Stage 4: Refresh Metadata And Provenance

This is the step that converts completed run outputs into branch-standard publishable outputs.

Preferred command pattern:

```bash
/path/to/geneset-extractor-dev/run/submit_<library>_models_cluster_apptainer.sh \
  --submit \
  --refresh_metadata_and_provenance
```

Typical supporting environment variables may include:

- `DESCRIPTION_TEMPLATE_TSV`
- `PROVENANCE_MIRROR_LOCAL_PREFIX`
- `PROVENANCE_MIRROR_REMOTE_PREFIX`
- `LOCAL_INPUT_SOURCE_MAP_TSV`
- library-specific output-root and log-root variables

This refresh step should:

- regenerate `geneset.model.json` if needed
- patch metadata descriptions from templates
- rewrite provenance to keep the graph connected
- update the provenance `GeneSet` description to match metadata
- rewrite GMT second-column descriptions
- preserve original files as:
  - `geneset.meta.json.orig`
  - `geneset.provenance.legacy.json.orig`
  - `genesets.gmt.orig`

This is the point at which outputs should become **publishable**.

## Publishable Output Definition

A model output should be treated as publishable only after the refresh step succeeds and the output now satisfies the shared contract.

That means:

- the output tree is in the standard model/partition layout
- `geneset.model.json` is present
- metadata descriptions are template-driven and model-specific
- provenance begins from the true initial inputs
- provenance is graph-connected across workflow and extractor stages
- local paths have been rewritten or sanitized where needed
- GMT names are stable
- GMT second-column descriptions are populated
- `.orig` files exist for rewritten artifacts

Running the main workflow alone is not enough.

## Stage 5: Publish Outputs

Only after refresh should the outputs be published.

Shared publish command:

```bash
/path/to/geneset-extractor-dev/run/publish_library_to_s3.sh [args...]
```

Typical publish behavior:

- publish all models for a library
- publish selected models only
- upload only the already-refreshed artifacts

Publishing should not be used to “fix” outputs. The outputs must already be publishable before this step.

## What Wrapper Commands A New Library Should Support

A new library should support the following usage patterns from its submit wrapper.

Minimum expected modes:

- `--submit`
- `--submit --write_model_only`
- `--submit --refresh_metadata_and_provenance`

Minimum expected filters:

- `--model_id`
- a partition filter when the library has a natural partition dimension

Recommended model filter behavior:

- accept a single model ID
- accept comma-delimited model IDs

Recommended partition filter behavior:

- accept one partition at a time unless there is a strong reason not to

## Example Lifecycle

For a new library `LIBRARY_X`, the expected lifecycle should look like this:

1. During development, validate sidecars:

```bash
submit_library_x_models_cluster_apptainer.sh --submit --write_model_only --model_id M1
```

2. Run the actual workflow:

```bash
submit_library_x_models_cluster_apptainer.sh --submit --model_id M1
```

3. Refresh outputs into publishable form:

```bash
submit_library_x_models_cluster_apptainer.sh --submit --refresh_metadata_and_provenance --model_id M1
```

4. Publish the refreshed outputs:

```bash
publish_library_to_s3.sh --local_output_root /path/to/library_x_all_models ...
```

## What To Avoid

Do not treat the following as acceptable final workflow patterns:

- a library that only has one-off Python scripts and no wrapper submit command
- a library that writes final `geneset.*` outputs directly from wrapper scripts without DIG owning workflow logic
- a library that has no `geneset.model.json`
- a library that requires manual editing of metadata or provenance after the run
- a library where publishable output is produced only by hand-editing files

## Acceptance Test For A New Library

Before calling a new library “done,” a user should be able to answer yes to all of the following:

- Can I write model sidecars without running the full workflow?
- Can I submit all models from a wrapper script?
- Can I submit one model or a filtered subset?
- Can I rerun refresh without rerunning the full workflow?
- After refresh, are the outputs publishable by branch standards?
- Can I publish those refreshed outputs without custom one-off fixes?

If the answer to any of these is no, the wrapper workflow is not finished yet.
