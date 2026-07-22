# Collaborator Library Onboarding Workflow Proposal

## Goal

Replace the current fork-heavy, submission-by-snapshot process with a simpler onboarding workflow that:

- does not require collaborators to know Git
- keeps `dig-gene-set-extractors` and `geneset-extractor-dev` as the canonical codebases
- standardizes what collaborators hand off for a new library
- makes it easier to review, integrate, run, refresh, and publish a library

## Problem With The Current Approach

The current process has worked for a small number of libraries, but it does not scale well.

Main pain points:

- collaborators submit forked codebases with different layouts and conventions
- wrapper logic, config structure, and output contracts drift from the branch standard
- integration work happens after the fact rather than during implementation
- outputs may be present, but it can be unclear whether the code and provenance align with canonical standards
- reviewing multiple fork snapshots is harder than reviewing structured, canonical inputs

## Proposed New Workflow

### Principle

Collaborators should primarily contribute:

- library-specific input data
- library-specific metadata
- library-specific workflow requirements
- library-specific configuration values

They should not be expected to:

- understand the internal architecture of both repos
- write canonical wrappers from scratch
- manage Git branches or PRs
- guess the correct publishability standard

### New Hand-Off Model

Instead of sending a forked codebase, each collaborator produces a **library onboarding bundle**.

That bundle is then integrated into the canonical repos by the maintainer or by a controlled integration workflow.

## Proposed Collaborator Deliverable

Each collaborator submits a single zipped onboarding bundle containing:

- `library_manifest.json`
- `library_questionnaire.tsv` or `.json`
- `config/`
- `inputs_manifest.tsv`
- `run_examples.md`
- `notes.md`
- optional small representative input files
- optional representative expected output examples

This bundle should be sufficient for the maintainer to:

- understand the data source
- understand the analysis partitions
- understand candidate model structure
- map the library onto the existing wrapper/DIG architecture

## What The Bundle Should Capture

### 1. Library identity

- library name
- data source name
- organism
- genome build
- assay type
- whether outputs are signed or unsigned
- whether outputs are per tissue, per study, per partition, per contrast, or global

### 2. Input inventory

- every external input file or directory
- source URL/URI for each input
- file role
- format
- whether it is required for rerunning the pipeline

### 3. Partitioning strategy

- what the natural unit of parallelism is
- whether the library is split by tissue, cohort, study, dataset, cell type, or contrast
- whether models run across all partitions or per partition

### 4. Model definitions

For each planned model:

- model ID
- model family
- short description
- what makes it distinct from the other models
- whether it starts from raw data or released differential expression
- expected naming pattern for gene sets

### 5. Workflow intent

- what upstream transformation is required
- what DIG workflow category best matches it
- whether a new DIG workflow or converter is likely needed

### 6. Expected outputs

- expected output root name
- expected partition directory structure
- expected model directory structure
- expected gene set naming pattern
- expected metadata/provenance requirements

## Canonical Integration Workflow

Once the onboarding bundle is received, the maintainer performs the canonical integration.

### Phase 1: Intake review

- validate the bundle against a required schema
- confirm that the input inventory is complete
- confirm that the proposed models are coherent
- confirm the natural partitioning and parallelization strategy

### Phase 2: Architecture decision

Decide whether the library can be implemented using:

- existing DIG workflow + existing converter
- existing DIG workflow + new converter
- new DIG workflow + existing converter
- new DIG workflow + new converter

### Phase 3: Canonical implementation

Implement in canonical repos only:

- DIG-side workflow and/or converter changes in `dig-gene-set-extractors`
- wrapper/config/run integration in `geneset-extractor-dev/<Library>/`

### Phase 4: Controlled run

Run the library in a controlled environment:

- local apptainer image
- cluster array if the natural partition supports it
- standardized refresh of metadata and provenance
- standardized publish preparation

### Phase 5: Validation

Run a publishability validator that checks:

- final output layout
- model sidecars
- metadata completeness
- provenance completeness
- GMT descriptions
- no local filesystem leakage
- `.orig` preservation

## Benefits

This approach:

- reduces fork sprawl
- removes Git knowledge as a prerequisite for collaborators
- centralizes integration into the canonical repos
- keeps standards consistent across libraries
- makes review easier
- makes provenance and publish preparation more predictable

## Recommended Supporting Components

To make this work well, the following should exist in `geneset-extractor-dev`.

### 1. Bundle schema

A machine-readable schema for the onboarding bundle:

- required files
- required fields
- allowed enumerations

### 2. Intake validator

A CLI validator that checks whether a collaborator bundle is complete and well-formed.

### 3. Library scaffold generator

A tool that converts a validated onboarding bundle into a starting library scaffold under:

- `geneset-extractor-dev/<Library>/config/`
- `geneset-extractor-dev/<Library>/planning/`
- `geneset-extractor-dev/<Library>/run/`
- `geneset-extractor-dev/<Library>/src/`

### 4. Publishability validator

A validator for generated outputs that checks conformance to the standards already used for:

- GTEx
- MoTrPAC
- HuBMAP
- LINCS_L1000

## Recommended Transition Plan

### Immediate

- stop asking collaborators to submit forked repos by default
- instead request onboarding bundles plus input data locations

### Near term

- define the onboarding bundle schema
- build a bundle validator
- build a scaffold generator

### Medium term

- generate canonical scaffolds automatically from the bundle
- use controlled canonical integration rather than external fork review as the default path

## Bottom Line

The best next step is not to keep improving fork review. The better path is to shift collaborators to a structured onboarding bundle model and keep implementation/integration inside the canonical repos.

This keeps the architecture you already built, but replaces the least scalable part of the process.
