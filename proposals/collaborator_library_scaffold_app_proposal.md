# Collaborator Library Scaffold App Proposal

## Short Answer

Yes. A local app is a practical way to remove Git as a prerequisite and standardize collaborator submissions.

The app should not try to run the full library pipeline by default. Its primary role should be to help a collaborator describe a new library in a structured way and produce a validated onboarding bundle that can be zipped and sent to the maintainer or to a central intake portal.

## Goal

Build a small local app that a collaborator can run on their own machine to:

- describe a new library
- register inputs and their source locations
- define partitions and candidate models
- generate scaffold/config files
- validate completeness
- package everything into a zip file for handoff

## Why An App Helps

Right now, collaborators often need to infer:

- what files are required
- what config shape is expected
- how models should be represented
- what output contract is expected

A guided app would replace guesswork with a structured intake process.

Benefits:

- no Git required
- fewer malformed submissions
- more consistent library definitions
- less maintainer time spent reconstructing intent

## Recommended Scope

The first version should be a **scaffold/intake app**, not a full execution platform.

It should focus on:

- data description
- model definition
- config generation
- packaging

It should not initially attempt to:

- execute DIG workflows
- manage cluster jobs
- publish to S3
- build full provenance

Those remain canonical maintainer-side tasks.

## Proposed App Outputs

The app should generate a library onboarding bundle with files such as:

- `library_manifest.json`
- `inputs_manifest.tsv`
- `model_plan.tsv`
- `partition_plan.tsv`
- `config/model_list.tsv`
- `config/model_manifest.tsv`
- `config/model_description_templates.tsv`
- `planning/pipeline_inputs.md`
- `planning/notes.md`
- `run_examples.md`
- `bundle_summary.md`

It should then create:

- `<library_name>_onboarding_bundle.zip`

## Proposed User Experience

### Step 1: Basic library information

The app asks for:

- library name
- source consortium or project
- assay type
- organism
- genome build
- high-level data type

### Step 2: Input registration

The app prompts the user to add:

- file paths
- directories
- URLs/URIs
- short descriptions of each input
- whether each input is raw, processed, metadata, annotation, or reference

### Step 3: Partition definition

The app asks:

- what are the natural partitions
- what can be parallelized independently
- what one unit of output represents

Examples:

- tissue
- study
- cohort
- analysis set
- cell type
- contrast

### Step 4: Model definition

The app asks for one or more models:

- model ID
- model family
- short description
- distinct algorithmic feature
- whether it starts from raw inputs or precomputed DE

### Step 5: Output expectations

The app asks:

- expected gene set naming pattern
- signed or unsigned
- whether outputs are per contrast or per partition
- whether a top-level aggregated GMT is expected

### Step 6: Validation

The app validates:

- required fields are present
- IDs are unique
- input references are complete
- models are defined coherently
- bundle structure is complete

### Step 7: Packaging

The app writes the bundle and zips it.

## Suggested Implementation Form

### Best first version

A simple local CLI app with a guided prompt flow.

Why:

- easiest to distribute
- easiest to maintain
- no browser/server requirements
- works well on cluster-adjacent systems

Possible form:

- Python CLI
- `questionary` or plain prompt-based interface
- writes JSON/TSV/Markdown files

### Good second version

A lightweight local web app:

- form-based UI
- local browser
- export bundle as zip

This could be better for less technical users, but it is more work and more moving pieces.

## Suggested Architecture

### Collaborator side

The collaborator runs:

- `library-onboard init`
- `library-onboard add-input`
- `library-onboard add-model`
- `library-onboard validate`
- `library-onboard package`

### Maintainer side

The maintainer runs:

- `library-onboard inspect <bundle.zip>`
- `library-onboard scaffold <bundle.zip>`

The scaffold command would populate a draft library under `geneset-extractor-dev/<Library>/`.

## What The App Should Not Decide Automatically

The app should collect structured information, but some decisions should remain maintainer-side:

- exact DIG workflow design
- whether new DIG code is required
- final wrapper implementation
- final provenance refresh strategy
- final S3 publication policy

## Optional Future Extensions

Later, the app could optionally support:

- generating a draft `geneset-extractor-dev/<Library>/` scaffold directly
- attaching representative small inputs
- generating a proposed run matrix
- generating a draft evaluation checklist
- uploading the zip directly to a central intake portal

## Recommended Development Plan

### Phase 1

Build the minimum viable app:

- guided CLI
- schema-backed bundle output
- zip packaging
- validation

### Phase 2

Add maintainer-side scaffold generation:

- generate config files
- generate planning docs
- generate placeholder run/src files

### Phase 3

Add portal support:

- upload onboarding bundle
- register collaborator metadata
- track intake status

## Bottom Line

Yes, a local onboarding app is feasible and would likely improve the process substantially.

The most useful first version is not a full execution app. It is a structured intake/scaffold app that:

- removes Git from the collaborator experience
- generates canonical config/scaffold artifacts
- produces a zip bundle for onboarding

That would fit your current architecture well and make future library intake much easier to manage.
