# Collaborator Onboarding Quickstart

## Purpose

This document explains what a collaborator should do when they have a dataset they want to submit through the automated onboarding system.

The process has two phases:

1. learn what kinds of libraries the system supports
2. start an onboarding bundle for the best matching workflow

## Phase 1: Learn The Available Options

Before starting a bundle, the collaborator should determine whether their data fits one of the supported automated workflow patterns.

### Step 1: List the supported workflow archetypes

Run:

```bash
bash geneset-extractor-dev/run/library_onboard.sh list-workflow-archetypes
```

This prints the currently supported high-level workflow types.

These describe the overall library shape, such as:

- directory of marker tables
- signature matrix
- released differential-expression tables
- counts plus metadata

### Step 2: List the supported extractor archetypes

Run:

```bash
bash geneset-extractor-dev/run/library_onboard.sh list-archetypes
```

This prints the supported final DIG extraction types.

These are the current extractor archetypes:

- `released_de_rna`
- `unsigned_term_gene`
- `signed_term_gene`

### Step 3: List the supported environment profiles

Run:

```bash
bash geneset-extractor-dev/run/library_onboard.sh list-environment-profiles
```

This prints the supported runtime environments.

These tell the collaborator whether their library is expected to run under:

- the standard geneset-extractor image
- an R-heavier image
- a custom approved image
- or a maintainer-only mode

### Step 4: Read the workflow guidance

The collaborator should also read:

- `geneset-extractor-dev/docs/dev/add_new_library/single_interaction_template_generator_collaborator_guide.md`
- `geneset-extractor-dev/proposals/workflow_archetype_schema_proposal.md`

Those documents explain how the system is structured and what kinds of outputs are expected.

## Phase 2: Choose The Best Match

The collaborator should choose:

1. a `workflow_archetype`
2. an `extractor_archetype`
3. an `environment_profile`

### Common choices

If the input is a directory of marker tables:

- `workflow_archetype = table_directory_marker_library`
- `extractor_archetype = unsigned_term_gene`

If the input is a signature matrix:

- `workflow_archetype = matrix_signature_library`
- `extractor_archetype = signed_term_gene`

If the input is one or more released differential-expression tables:

- `workflow_archetype = released_de_multi_partition`
- `extractor_archetype = released_de_rna`

If the input is counts plus sample metadata:

- `workflow_archetype = bulk_counts_multi_model`
- `extractor_archetype = released_de_rna`

If the input is counts plus metadata and the collaborator needs a timecourse or training-style workflow:

- `workflow_archetype = raw_counts_training_timecourse`
- `extractor_archetype = released_de_rna`

If the library does not fit cleanly:

- `workflow_archetype = custom_hybrid`

That does not mean the library is rejected. It means the collaborator should still prepare a standard bundle, but the library may require more maintainer review.

## Phase 3: Start The First Real Step

Once the collaborator has selected the workflow and extractor archetypes, the first real step is to initialize an onboarding bundle.

Example:

```bash
bash geneset-extractor-dev/run/library_onboard.sh init \
  --library_name MyLibrary \
  --out_dir ./my_library_bundle \
  --archetype unsigned_term_gene \
  --workflow_archetype table_directory_marker_library \
  --environment_profile geneset_extractor_standard
```

Notes:

- `--archetype` is the legacy name used by the current CLI for the extractor archetype
- `--workflow_archetype` is the library-level workflow type
- `--environment_profile` is the runtime expectation

After running `init`, the collaborator has a bundle directory that becomes the source of truth for the rest of the submission process.

## What To Do Next

After `init`, the collaborator should proceed in this order:

1. update `library_manifest.json` with organism, genome build, and project metadata
2. register each required input with `add-input`
3. define partitions with `add-partition`
4. define models with `add-model`
5. run bundle validation
6. generate the runnable package
7. run the package
8. validate outputs
9. package the final submission archive

## Minimal Example Of The Next Commands

Validate the bundle:

```bash
bash geneset-extractor-dev/run/library_onboard.sh validate \
  --bundle_dir ./my_library_bundle
```

Generate the runnable package:

```bash
bash geneset-extractor-dev/run/library_onboard.sh generate-package \
  --bundle_dir ./my_library_bundle \
  --out_dir ./my_library_package
```

## Summary

The collaborator should think of the process as:

1. inspect supported workflow and extractor options
2. choose the closest workflow shape
3. initialize a bundle
4. fill in inputs, partitions, and models
5. validate and generate the package

That is the cleanest entry point into the automated onboarding system.
