# Single-Interaction Template-Driven Library Generator Proposal

## Goal

Define a new collaborator workflow that allows a submitter to:

- provide their input data and library description once
- generate runnable library code locally
- run the pipeline locally or on cluster
- produce standardized GMT files, metadata, provenance, and sidecars
- send back a single finished submission archive

This proposal is meant to eliminate iterative back-and-forth for libraries that fit known patterns.

## Core Idea

The collaborator app should not behave like a generic code generator for arbitrary bioinformatics pipelines.

Instead, it should behave like a **template-driven library generator** that assembles a runnable library from a controlled catalog of:

- input archetypes
- workflow templates
- converter templates
- model templates
- refresh templates
- validation templates
- packaging templates

Under this model, the collaborator does not invent the library structure. They select and parameterize an approved library type.

## Why This Is Necessary

If the goal is a single collaborator interaction that results in:

- generated code
- generated GMTs
- generated metadata/provenance
- a final archive ready for review

then the app must be opinionated.

A free-form app would produce too much drift in:

- wrapper structure
- config naming
- run scripts
- provenance behavior
- output layout
- publish readiness

The only scalable one-shot model is a constrained one.

## Submission Types

Under this proposal, every new collaborator submission is classified into one of two categories.

### 1. Template-compatible library

A library is template-compatible if it can be expressed using an already supported canonical pattern.

Examples:

- released differential-expression table -> `rna_deg`
- counts + sample metadata -> `rna_de_prepare` -> `rna_deg`
- unsigned term-gene table -> `unsigned_term_gene`
- signed term-gene table -> `signed_term_gene`
- perturbation signature matrix -> approved perturbation workflow + converter
- single-cell program loadings -> approved scRNA program converter

These can be handled in a single collaborator interaction.

### 2. Custom library

A library is custom if it requires:

- new DIG workflow logic
- new DIG converter logic
- new extraction semantics not represented by existing templates
- nonstandard provenance behavior

These cannot reliably be handled in a single collaborator interaction.

For custom libraries, the app should stop early and emit:

- a structured onboarding bundle
- a note that maintainer-side implementation is required

## Recommended App Behavior

### Collaborator path for template-compatible libraries

The collaborator runs a local app that:

1. identifies the correct archetype
2. collects structured metadata
3. generates a runnable library package from canonical templates
4. runs the package locally or on cluster
5. refreshes metadata and provenance
6. validates outputs
7. packages the final submission

### Collaborator path for custom libraries

The app:

1. collects structured metadata
2. generates an onboarding bundle only
3. does not generate runnable code
4. explicitly marks the submission as requiring maintainer-side implementation

## What The App Must Generate For Template-Compatible Libraries

The generated package should include:

- library-specific config files
- model manifests
- description templates
- wrapper build scripts
- apptainer run scripts
- refresh scripts
- validation scripts
- packaging manifest

It should also generate:

- a local run plan
- example commands
- output manifest template

## Proposed End-To-End Collaborator Workflow

### Step 1: Start a new library

The collaborator launches the app and provides:

- library name
- assay type
- organism
- genome build
- high-level input data type

### Step 2: Archetype selection

The app decides whether the library matches one of the supported archetypes.

Examples:

- released DE table
- counts-based bulk differential expression
- term-gene table
- single-cell program loadings
- perturbation signature matrix

If no archetype matches, the app falls back to onboarding-bundle-only mode.

### Step 3: Input registration

The collaborator adds:

- raw files
- processed files
- metadata files
- annotation files
- source URLs/URIs

### Step 4: Partition and model definition

The collaborator provides:

- natural partitions
- model count
- model IDs
- what distinguishes each model

### Step 5: Generate runnable package

The app generates a library package containing:

- `config/`
- `src/`
- `run/`
- `planning/`
- validation utilities

All generated files must come from canonical templates.

### Step 6: Execute

The collaborator runs the generated commands, ideally through Apptainer.

### Step 7: Refresh and validate

The app runs:

- metadata refresh
- provenance refresh
- local path sanitization
- `.orig` preservation
- output validation

### Step 8: Package final submission

The app creates a final zip containing:

- generated code
- configs
- planning docs
- logs
- output manifests
- GMTs
- metadata
- provenance
- validation report

## Required Library Archetypes

The first version should support only a small number of canonical patterns.

### Archetype A: Released DE table

Input:

- one released differential expression table per partition

Pipeline:

- normalize column mapping
- run `rna_deg` conversion
- emit signed or unsigned gene sets

### Archetype B: Counts + metadata bulk RNA-seq

Input:

- expression counts
- sample metadata

Pipeline:

- `rna_de_prepare`
- `rna_deg`

### Archetype C: Unsigned term-gene table

Input:

- a table of term-to-gene relationships

Pipeline:

- `unsigned_term_gene`

### Archetype D: Signed term-gene table

Input:

- signed table with up/down or signed effect values

Pipeline:

- `signed_term_gene`

### Archetype E: Single-cell program loadings

Input:

- program-by-gene or gene-by-program matrix

Pipeline:

- approved scRNA converter template

### Archetype F: Perturbation signature matrix

Input:

- perturbation-by-gene matrix or per-perturbation long table

Pipeline:

- approved perturbation template

## Generated Package Layout

For template-compatible libraries, the app should emit a runnable package with a branch-standard layout:

```text
<Library>/
  config/
    model_list.tsv
    model_manifest.tsv
    model_description_templates.tsv
    partition_list.tsv
  src/
    build_<library>_genesets.py
    run_<library>_model.py
  run/
    build_<library>_genesets.sh
    build_<library>_genesets_apptainer.sh
    refresh_<library>_metadata_and_provenance.sh
    refresh_<library>_metadata_and_provenance_apptainer.sh
    validate_<library>_outputs.sh
  planning/
    pipeline_inputs.md
    package_summary.md
    archetype_selection.md
  outputs/
    <optional local staging area>
```

The package may later be merged into canonical `geneset-extractor-dev/<Library>/`, but the collaborator should be able to run it standalone.

## Apptainer Strategy

Apptainer should be the default execution mode for template-compatible packages.

The app should generate:

- non-apptainer commands
- apptainer commands

If the archetype requires only the existing `geneset-extractor` image, the generated package should use that directly.

If an archetype requires a different environment, the app should either:

- emit a dedicated `.def` file template
- or reject the archetype as not single-interaction-compatible

The preferred rule is:

- only archetypes runnable under approved images are eligible for one-shot collaborator execution

## Validation Requirements

The app must validate before packaging the final submission.

Required checks:

- output directories exist
- required GMTs exist
- metadata JSON exists
- provenance JSON exists
- model sidecars exist
- no local filesystem paths remain in final metadata/provenance
- `.orig` files exist for rewritten artifacts
- GMT second-column descriptions are populated
- output tree follows branch conventions

If validation fails, the app should refuse to package the final submission as publish-candidate output.

## Final Submission Archive

The collaborator should send back one zip file containing:

- generated library package
- generated output tree
- validation report
- run logs
- exact commands used

Suggested contents:

```text
<library_name>_submission/
  code/
  outputs/
  validation/
  run_logs/
  submission_manifest.json
  commands.md
```

## Submission Manifest

The final archive should include a machine-readable manifest with fields such as:

- `library_name`
- `archetype`
- `tool_version`
- `generated_at`
- `apptainer_used`
- `apptainer_image`
- `models`
- `partitions`
- `output_root`
- `validation_status`
- `known_limitations`

## Maintainer Review Process Under This Model

Once a collaborator sends the archive, the maintainer reviews:

1. whether the library was generated from an approved archetype
2. whether the generated code matches template expectations
3. whether the outputs validate
4. whether provenance and metadata are publish-safe

The maintainer no longer needs to reconstruct the collaborator’s intent from a forked repo.

## Advantages

This model gives:

- a single collaborator interaction
- runnable code generation
- standardized output generation
- lower Git burden
- lower integration ambiguity

It also gives a clean reason to reject unsupported one-shot libraries:

- they are not template-compatible

## Limitations

This model will not cover every library.

It is strongest for libraries whose analysis can be represented as:

- parameterized use of existing DIG workflows
- parameterized use of existing converters
- standard wrapper/config/output behavior

It is weakest for libraries requiring genuinely new methods.

That limitation is acceptable, because it makes the one-shot pathway explicit rather than pretending every library can be fully automated.

## Recommended Implementation Plan

### Phase 1

Build template-compatible onboarding and package generation for:

- released DE tables
- counts + metadata bulk RNA-seq
- signed/unsigned term-gene tables

### Phase 2

Add:

- perturbation templates
- scRNA program templates

### Phase 3

Add:

- cluster submission template generation
- optional standalone validation HTML summary

## Decision Rule

Before implementation, every new library should be evaluated with this question:

> Can this library be expressed as a parameterized instance of an approved archetype under an approved Apptainer environment?

If yes:

- allow the single-interaction workflow

If no:

- require onboarding-bundle-only mode and maintainer-side implementation

## Bottom Line

If you want collaborators to submit a single archive that already contains runnable code, GMT files, metadata, and provenance, the correct strategy is not a generic app. It is a strict template-driven library generator with a limited set of approved archetypes.

That is the only realistic way to get one-shot collaborator submissions while preserving branch standards.
