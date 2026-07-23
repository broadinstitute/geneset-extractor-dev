# Workflow-Archetype Onboarding Implementation Plan

## Goal

Implement the next version of the collaborator onboarding system so it can support future libraries shaped like the maintained canonical set:

- `GTEx`
- `MoTrPAC`
- `LINCS_L1000`
- `HuBMAP`
- environment-special or partially custom cases such as `LIGER`

This plan is intentionally additive. It should not interrupt the current canonical library codepaths while the new system is being built.

## Current Limitation

The current implementation in `library_onboard.py` is centered on three converter-level archetypes:

- `released_de_rna`
- `unsigned_term_gene`
- `signed_term_gene`

That is enough for simple table-to-library cases, but not for the multi-step workflows that real libraries need.

## Design Principle

The new system should remain template-driven, but the templates need to be elevated from **converter templates** to **library workflow templates**.

The collaborator should still not be writing arbitrary code by hand.

Instead, they should parameterize a controlled workflow archetype with:

- structured inputs
- structured partitions
- structured model families
- approved naming rules
- approved environment profile

## Proposed Scope

### In scope

- workflow archetype definitions
- schema expansion
- generator support for multi-step workflows
- environment profiles
- model-family parameterization
- provenance and naming contracts
- hybrid fallback mode

### Out of scope for first implementation

- automatic acceptance of arbitrary custom libraries
- dynamic code generation from free-form natural language
- unrestricted user-authored workflow scripting

## Implementation Strategy

Build the new system in phases so the current onboarding tooling remains usable throughout.

## Phase 1: Add Schema Support

Primary deliverable:

- extend the collaborator bundle schema to carry workflow-level metadata

Required code updates:

- expand `library_config.json` generation
- add `workflow_manifest.json`
- add `environment_profile.json`
- extend input, partition, and model manifest schemas

Required code locations:

- `geneset-extractor-dev/src/library_onboard.py`

Phase-1 success criteria:

- bundles can declare `workflow_archetype`
- bundles can declare `extractor_archetype`
- bundles can declare `environment_profile`
- current converter-only flows still validate

## Phase 2: Add Workflow Archetype Registry

Primary deliverable:

- introduce a `WORKFLOW_ARCHETYPES` registry parallel to `ARCHETYPES`

Suggested first entries:

- `bulk_counts_multi_model`
- `released_de_multi_partition`
- `raw_counts_training_timecourse`
- `matrix_signature_library`
- `table_directory_marker_library`
- `custom_hybrid`

Each workflow archetype should declare:

- supported input roles
- supported partition shape
- supported model-family shape
- environment profile
- required workflow options
- expected intermediate file roles
- final extractor compatibility

Phase-2 success criteria:

- onboarding can list supported workflow archetypes
- bundle validation can reject incompatible combinations
- archetype detection is no longer extractor-only

## Phase 3: Support Library-Level Code Generation

Primary deliverable:

- generated packages can emit multi-step wrappers, not just converter wrappers

Generated package must support:

1. workflow step
2. extractor step
3. metadata/provenance refresh
4. validation
5. packaging

New generated artifacts should include:

- workflow-aware `src/generated_library_runtime.py`
- workflow-aware run wrappers
- model-family-aware manifests
- environment-aware example commands

Phase-3 success criteria:

- generated package contains an explicit workflow stage
- converter invocation is downstream of workflow emission
- package still emits standard outputs and sidecars

## Phase 4: Add Model-Family Templates

Primary deliverable:

- support reusable model-family parameter blocks under a workflow archetype

Examples to support:

- GTEx-style `AB`, `AC`, `HZ`
- MoTrPAC-style `TR`, `TW`, `HZ`
- LINCS-style matrix variants
- HuBMAP-style released vs augmented table modes

Model-family templates should define:

- model label
- unique algorithmic feature
- workflow option overrides
- naming variable overrides
- description templates

Phase-4 success criteria:

- collaborator can define multiple models without custom code
- model sidecars remain standardized
- user-facing descriptions can expose model-specific variables

## Phase 5: Add Environment Profiles

Primary deliverable:

- generator can emit runtime wrappers appropriate to approved environments

Initial environment profiles:

- `geneset_extractor_standard`
- `geneset_extractor_r_heavy`
- `custom_approved_image`
- `maintainer_only`

This phase is important for future cases like `LIGER`, where the workflow may require a different image profile than the current standard environment.

Phase-5 success criteria:

- generated package states its expected runtime
- app can refuse unsupported single-interaction environments
- app can fall back to `custom_hybrid` or maintainer-side mode when needed

## Phase 6: Add Hybrid Bundle Mode

Primary deliverable:

- support a controlled fallback for libraries that are close to template-compatible but still need limited custom workflow code

The hybrid mode should still standardize:

- manifest schema
- run wrapper layout
- refresh behavior
- output contract
- package submission layout

But it may allow:

- a limited custom workflow module
- a maintainer review gate before execution

Phase-6 success criteria:

- collaborator can still submit one standardized bundle
- maintainer can still use the existing review/staging tools
- libraries that are not pure archetype instances are no longer forced into ad hoc repo forks

## Phase 7: Extend Maintainer Review Tooling

Primary deliverable:

- update review and staging tools to understand workflow archetypes

Tools already added:

- `review_submission_archive.py`
- `stage_submission_as_canonical_library.py`

These should be extended to validate:

- `workflow_archetype`
- environment profile
- expected workflow command chain
- intermediate file expectations
- model-family declarations

Phase-7 success criteria:

- maintainer-side tools can distinguish template-only, template-plus-parameters, and hybrid submissions
- publishability reports mention workflow archetype compatibility

## Phase 8: Pilot With Existing Canonical Libraries

Primary deliverable:

- prove the new abstractions against the existing maintained libraries

Recommended pilot order:

1. `HuBMAP`
2. `LINCS_L1000`
3. `MoTrPAC` released DEA style
4. `GTEx`
5. `MoTrPAC` raw-count workflows

Reason:

- `HuBMAP` and `LINCS_L1000` are closest to workflow-plus-converter patterns
- `GTEx` and raw-count `MoTrPAC` are more complex and should come later

Phase-8 success criteria:

- each pilot library can be represented declaratively
- generated manifests match the actual library behavior
- output naming and provenance remain publishable

## Proposed File and Code Changes

### New data structures

Add to `library_onboard.py`:

- `WORKFLOW_ARCHETYPES`
- `ENVIRONMENT_PROFILES`

### New generated config files

- `config/workflow_manifest.json`
- `config/environment_profile.json`

### Expanded generated manifests

- `config/inputs_manifest.tsv`
- `config/partition_list.tsv`
- `config/model_list.tsv`
- `config/model_manifest.tsv`

### Possible future refactor

If `library_onboard.py` becomes too large, split it into:

- `onboard_schema.py`
- `onboard_workflow_archetypes.py`
- `onboard_codegen.py`
- `onboard_validation.py`

This should happen only after the new schema is stable.

## Backward Compatibility

The current system should remain valid for simple converter-only cases.

Backward compatibility rule:

- if `workflow_archetype` is omitted, infer a legacy simple workflow from the current `archetype`

That allows the existing onboarding tool and bundles to keep working while the richer model is introduced.

## Risks

### Risk 1: Overgeneralization

If the workflow archetypes are too generic, the system becomes another free-form code generator.

Mitigation:

- keep archetype catalog small
- force explicit environment profiles
- require strict output contracts

### Risk 2: Archetype drift

Collaborators may try to force incompatible libraries into a near match.

Mitigation:

- add explicit `custom_hybrid` mode
- make the app reject unsupported combinations early

### Risk 3: Template sprawl

Too many special cases could make the generator hard to maintain.

Mitigation:

- only promote a new workflow archetype when it reflects a recurring pattern
- keep one-off behaviors in hybrid mode until proven reusable

## Recommended First Implementation Slice

The smallest high-value build should do the following:

1. add `workflow_archetype` to the schema
2. add `WORKFLOW_ARCHETYPES`
3. implement:
   - `table_directory_marker_library`
   - `matrix_signature_library`
   - `released_de_multi_partition`
4. add `environment_profile`
5. update review/staging tools to read these fields

This slice would immediately cover the easiest future analogs of:

- `HuBMAP`
- `LINCS_L1000`
- part of `MoTrPAC`

## Recommendation

Proceed with the new onboarding system as a staged, additive migration:

- preserve the current converter-only onboarding path
- add workflow archetypes above it
- use the maintained libraries as the source of truth for the abstraction design
- allow hybrid fallback instead of forcing collaborators into full custom forks

That is the most realistic path to supporting future libraries that resemble the maintained codebase while still preserving the benefits of single-interaction, template-driven onboarding.
