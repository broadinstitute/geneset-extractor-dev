# Post-Submission Maintainer Onboarding Workflow

## Purpose

This document describes what happens **after** a collaborator returns a completed archive produced through the single-interaction template-driven generator workflow.

At this stage, onboarding shifts from:

- collaborator-side bundle creation and execution

to:

- maintainer-side intake
- canonicalization
- reproducibility review
- publish readiness review

## What You Receive

The collaborator should return one final submission archive containing:

- generated library package code
- generated config files
- planning documents
- output tree
- logs
- metadata
- provenance
- GMT files
- validation report

This archive is the starting point for maintainer-side onboarding.

## High-Level Maintainer Workflow

Once the archive is received, use this process:

1. intake the submission
2. confirm archetype compatibility
3. validate the returned outputs
4. decide whether the submission is publishable as-is
5. decide whether the library should be promoted into canonical maintenance
6. if accepted, canonicalize the code and outputs
7. perform a spot rerun or representative rerun
8. move to publish preparation

## Phase 1: Intake The Submission

Create a working intake directory and unpack the archive.

At intake, record:

- collaborator name
- date received
- archive filename
- claimed library name
- claimed archetype
- any claimed supported models
- any claimed supported partitions

You should also capture:

- whether Apptainer was used
- which image name was used
- whether DIG was bundled or referenced externally

## Phase 2: Confirm Archetype Compatibility

The first major question is whether the returned package is truly a valid instance of the archetype it claims to use.

Examples:

- `released_de_rna`
- `unsigned_term_gene`
- `signed_term_gene`

Check:

- does the generated code match the expected template behavior
- do the config files align with the archetype
- are the required options present
- does the run logic call the expected DIG converter or workflow
- does the output shape match the expected archetype

If the submission does **not** actually match the claimed archetype, it should not be promoted as a template-compatible library.

At that point, it should be reclassified as either:

- a custom library requiring maintainer-side implementation
- or a submission needing substantial repair

## Phase 3: Validate The Returned Outputs

Before deciding whether the library is accepted, validate the returned artifacts.

### Output-level checks

Confirm:

- expected output directories exist
- expected models exist
- expected partitions exist
- `genesets.gmt` files exist
- `geneset.meta.json` files exist
- `geneset.provenance.json` files exist
- `geneset.model.json` files exist

### Metadata and provenance checks

Confirm:

- no collaborator-local `/home/`, `/Users/`, `/humgen/`, or other machine-specific filesystem paths remain in final metadata or provenance
- final provenance reflects the actual external inputs needed to rerun the analysis
- provenance command chain is complete for the archetype
- metadata and provenance descriptions agree

### GMT checks

Confirm:

- second-column descriptions are populated
- gene set names follow an acceptable naming scheme
- signed outputs use consistent `up` / `dn` labels where expected

### Preservation checks

Confirm:

- rewritten artifacts preserve `.orig` copies where expected

## Phase 4: Decide Whether The Outputs Are Publishable As-Is

At this stage, answer a narrow question:

> Can I publish these outputs now, even if I do not yet promote the code into canonical maintenance?

Possible outcomes:

### A. Publishable as-is

The outputs:

- validate
- have complete provenance
- have acceptable metadata
- have no local path leakage
- have acceptable GMT naming and descriptions

In this case, the outputs may be ready for publication even before deeper code integration.

### B. Publishable with minor repair

The outputs are close, but need:

- metadata refresh
- provenance refresh
- naming cleanup
- GMT description repair
- path sanitization

In this case, the maintainer can repair the artifacts before publication.

### C. Not publishable yet

The outputs are missing:

- complete provenance
- acceptable metadata
- required files
- stable naming
- or they do not reflect the claimed workflow

In this case, the submission is not ready for publication.

## Phase 5: Decide Whether To Promote The Library Into Canonical Maintenance

Publishability and canonical onboarding are related, but not identical.

The second major question is:

> Should this library become a maintained canonical library inside `geneset-extractor-dev`?

That requires more than just good output artifacts.

Confirm:

- the generated package is understandable
- the package is stable enough to rerun later
- the library structure is worth preserving long-term
- the archetype mapping is correct
- the maintainer can operate it without needing the collaborator again

If yes, the library moves into canonical onboarding.

## Phase 6: Canonicalize The Library

If the library is accepted, move it into the canonical codebase in a controlled way.

### Recommended canonical target

Create:

- `geneset-extractor-dev/<Library>/config/`
- `geneset-extractor-dev/<Library>/planning/`
- `geneset-extractor-dev/<Library>/run/`
- `geneset-extractor-dev/<Library>/src/`

### What to move or regenerate

Carry over:

- model lists
- manifests
- description templates
- planning notes
- stable run wrappers

Do **not** assume that every generated file should be copied verbatim.

Instead:

- normalize names
- normalize wrapper patterns
- normalize docs
- normalize any environment-specific command text

### DIG relationship

If the archetype used only existing DIG entrypoints, no DIG changes may be needed.

If the package reveals missing DIG functionality, then the library is not purely template-compatible and may need deeper integration work.

## Phase 7: Perform A Representative Rerun

Before treating the library as canonically onboarded, rerun a small representative subset yourself.

This rerun should use:

- your own environment
- your own Apptainer image
- your own DIG checkout

At minimum, rerun:

- one model
- one partition

If the library has multiple important model classes or partition types, consider one representative run for each.

The goal is to answer:

- can I reproduce the collaborator’s output from the submitted package and inputs
- are the outputs stable under a controlled rerun
- does the library behave as expected without collaborator-specific hidden state

## Phase 8: Final Publish Preparation

Once the outputs validate and the library is either accepted or accepted provisionally, prepare for publication.

This includes:

- final metadata refresh if needed
- final provenance refresh if needed
- final mirror URI rewriting if needed
- publish manifest generation
- optional S3 upload preparation

If the outputs were already publish-safe when submitted, this phase may be minimal.

## Recommended Maintainer Decision Outcomes

After post-submission onboarding, record one of the following decisions.

### 1. Accepted for publication and canonical onboarding

Use when:

- outputs are publishable
- code/package is accepted into canonical maintenance

### 2. Accepted for publication only

Use when:

- outputs are publishable
- but code is not yet suitable for canonical maintenance

### 3. Accepted pending maintainer-side repairs

Use when:

- the submission is structurally sound
- but final artifacts need repair before publication

### 4. Not accepted as submitted

Use when:

- the archetype claim is invalid
- provenance is incomplete
- metadata is unacceptable
- or outputs are not reproducible enough to trust

## Suggested Maintainer Checklist

Use this checklist for every returned archive.

### Intake

- archive received
- archive unpacked successfully
- library name identified
- archetype identified
- collaborator recorded

### Template review

- archetype matches generated code
- config matches archetype
- DIG entrypoints are as expected

### Output review

- outputs exist
- sidecars exist
- metadata exists
- provenance exists
- GMT descriptions are populated
- no local path leakage

### Reproducibility review

- inputs are identifiable
- command chain is complete
- representative rerun succeeded

### Canonical onboarding review

- library is worth maintaining
- config is reusable
- run wrappers can be normalized
- planning docs are sufficient

### Publish review

- publish-safe metadata
- publish-safe provenance
- acceptable names and descriptions
- ready for packaging/upload

## Relationship To The Collaborator Workflow

The collaborator-side workflow ends when the final archive is sent back.

The maintainer-side workflow begins when that archive is received.

So the overall system becomes:

1. collaborator uses the template generator
2. collaborator returns a single archive
3. maintainer performs post-submission onboarding
4. maintainer either:
   - publishes the outputs
   - promotes the library into canonical maintenance
   - or rejects / repairs the submission

## When This Workflow Works Best

This post-submission model works best when:

- the collaborator used a supported template-compatible archetype
- the generated package was not manually altered in major ways
- the final outputs passed the generated validator
- the returned archive contains enough information to rerun a representative subset

## Bottom Line

After the collaborator returns the archive, onboarding is no longer about building the library. It is about deciding whether the returned package and outputs are acceptable, whether they are publishable, and whether the library should be promoted into canonical `geneset-extractor-dev` maintenance.

That post-submission maintainer workflow is the second half of the single-interaction model.
