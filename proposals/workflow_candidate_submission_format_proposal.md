# Workflow Candidate Submission Format Proposal

## Goal

Define a standard submission format that allows collaborators to propose a **new workflow archetype candidate** without forcing them to fork the full repositories in an ad hoc way.

The purpose is to let collaborators like Trang submit:

- the workflow logic needed to reproduce their GMTs
- the workflow metadata and input contract
- a small validation harness
- representative expected outputs

in a form that is easy for the maintainer to inspect, test, and promote into a canonical workflow archetype.

## Core Principle

A collaborator-submitted workflow should not be accepted automatically as a first-class archetype.

Instead, it should enter the system as a:

- `workflow_candidate`

The maintainer then decides whether to:

1. keep it as a one-off hybrid submission
2. adapt it into a canonical reusable workflow archetype
3. reject it as incompatible with the branch standards

## Why This Is Needed

The current collaborator pattern often looks like this:

- collaborator forks `dig-gene-set-extractors`
- collaborator forks `geneset-extractor-dev`
- collaborator adds custom workflow logic
- collaborator submits both forks plus outputs

That gives the maintainer too much to reverse-engineer:

- what the real workflow contract is
- what inputs are actually required
- what outputs are expected at each step
- how provenance is supposed to begin
- whether the workflow is reusable

A workflow-candidate submission format would replace that with a single structured bundle.

## Workflow Candidate Model

Every collaborator-submitted new workflow should be treated as one of:

1. **existing canonical workflow archetype**
2. **custom hybrid library**
3. **workflow candidate**

### Existing canonical workflow archetype

The library fits one of the already supported workflow archetypes and needs only configuration.

### Custom hybrid library

The library is one-off and may never be worth promoting into a reusable workflow archetype.

### Workflow candidate

The collaborator believes the workflow is coherent enough that it could become a reusable archetype for future libraries.

That is the new category proposed here.

## Recommended Collaborator Experience

The collaborator should be able to say:

> My data do not fit the current workflow archetypes, but I can supply a small workflow implementation and a structured spec that shows how the workflow works.

The onboarding system should then support a mode like:

```bash
bash geneset-extractor-dev/run/library_onboard.sh init \
  --library_name IGVF \
  --out_dir ./IGVF_bundle \
  --archetype signed_term_gene \
  --workflow_archetype custom_hybrid
```

and then allow the collaborator to attach a workflow-candidate payload under a fixed subdirectory.

## Proposed Submission Structure

The collaborator submission bundle should contain the normal onboarding files plus a workflow-candidate directory.

Suggested layout:

```text
<bundle_root>/
  bundle_manifest.json
  library_manifest.json
  questionnaire.json
  inputs_manifest.tsv
  partition_plan.tsv
  model_plan.tsv
  run_examples.md
  notes.md
  workflow_candidate/
    workflow_spec.json
    environment_profile.json
    entrypoint_contract.json
    implementation/
      run_workflow_candidate.py
      README.md
    tests/
      fixture_manifest.json
      expected_outputs_manifest.json
      run_candidate_smoke_test.sh
    examples/
      sample_input_manifest.tsv
      sample_output_manifest.tsv
    docs/
      workflow_rationale.md
      provenance_expectations.md
      naming_contract.md
```

## Required Files

### `workflow_candidate/workflow_spec.json`

This is the main declaration of the candidate workflow.

It should define:

- workflow candidate name
- version
- source library
- intended reusable scope
- input contract
- partition contract
- model-family contract
- intermediate outputs
- final extractor compatibility
- environment profile

Suggested shape:

```json
{
  "workflow_candidate_name": "igvf_perturbseq_released_de",
  "version": "0.1.0",
  "library_name": "IGVF",
  "candidate_status": "proposed",
  "intended_scope": "released perturb-seq differential-expression tables to signed gene sets",
  "final_extractor_archetypes": [
    "signed_term_gene"
  ],
  "partition_axis": "analysis_set",
  "model_axis": "perturbseq_model",
  "supports_apptainer": true,
  "environment_profile": "geneset_extractor_standard",
  "intermediate_outputs": [
    "signed_term_gene_tsv"
  ]
}
```

### `workflow_candidate/environment_profile.json`

This states the runtime assumptions for the workflow candidate.

It should be compatible with the canonical environment-profile model already introduced for the automated onboarding system.

Suggested fields:

- `environment_profile`
- `python_required`
- `r_required`
- `apptainer_image_required`
- `additional_packages`
- `notes`

### `workflow_candidate/entrypoint_contract.json`

This is critical.

It defines the fixed CLI contract for the workflow candidate implementation.

The maintainer should not have to infer the interface from code.

Suggested fields:

- `entrypoint`
- `language`
- `required_arguments`
- `optional_arguments`
- `input_roles_consumed`
- `output_files_emitted`
- `exit_behavior`

Example:

```json
{
  "entrypoint": "implementation/run_workflow_candidate.py",
  "language": "python",
  "required_arguments": [
    "--input_manifest_tsv",
    "--partition_id",
    "--model_id",
    "--out_dir"
  ],
  "optional_arguments": [
    "--work_dir",
    "--overwrite"
  ],
  "output_files_emitted": [
    "prepared_signed_term_gene.tsv",
    "workflow_manifest.json"
  ]
}
```

### `workflow_candidate/implementation/run_workflow_candidate.py`

This is the actual collaborator-supplied workflow implementation.

Rules:

- it must be a small, self-contained wrapper
- it must honor the declared CLI contract exactly
- it must write outputs only under the supplied `--out_dir`
- it must not rely on hidden shell state
- it must not modify files outside the working directories

The maintainer should be able to run it in isolation.

### `workflow_candidate/implementation/README.md`

This explains:

- what the workflow does
- how it maps source inputs to intermediate outputs
- what assumptions it makes
- what parts are library-specific versus reusable

### `workflow_candidate/tests/fixture_manifest.json`

This defines the minimal example inputs needed to test the candidate workflow.

It should be small enough for the maintainer to run quickly.

### `workflow_candidate/tests/expected_outputs_manifest.json`

This should list the expected outputs from the fixture test:

- output filenames
- expected row counts
- expected column names
- expected GMT counts if applicable

### `workflow_candidate/tests/run_candidate_smoke_test.sh`

This should be a single explicit command sequence that the maintainer can run to verify the workflow candidate behaves as described.

### `workflow_candidate/examples/sample_input_manifest.tsv`

This should show a realistic example of how the collaborator expects actual inputs to be registered.

### `workflow_candidate/examples/sample_output_manifest.tsv`

This should show the expected intermediate and final outputs.

### `workflow_candidate/docs/workflow_rationale.md`

This explains:

- why the collaborator believes the workflow deserves promotion into a reusable archetype
- what recurring pattern it captures
- how it differs from existing archetypes

### `workflow_candidate/docs/provenance_expectations.md`

This is essential for publishability.

It should explicitly describe:

- what the first provenance input nodes should be
- what intermediate files should appear in the graph
- what final converter step should appear
- how local paths should be replaced during refresh

### `workflow_candidate/docs/naming_contract.md`

This defines:

- GMT naming pattern
- metadata description variables
- provenance description variables
- model-sidecar variables

Without this, promotion into a canonical archetype becomes much harder.

## Required Behavioral Contract

The workflow candidate must obey these rules:

### 1. Fixed entrypoint contract

The implementation must not require undocumented arguments or hidden environment state.

### 2. Deterministic intermediate output

It must emit a declared intermediate file in a standard format, usually one of:

- `prepared_de.tsv`
- `prepared_signed_term_gene.tsv`
- `prepared_unsigned_term_gene.tsv`

### 3. Compatible final extractor

The candidate should terminate in an already supported extractor archetype whenever possible.

That is the preferred model:

- custom workflow preparation
- canonical DIG converter

### 4. Clean provenance start point

The workflow-candidate docs must explain what the provenance should begin from.

### 5. Reusable naming contract

The workflow cannot rely only on one-off naming embedded in code.

### 6. No hidden system assumptions

The workflow should not rely on:

- shell startup files
- hard-coded local directories
- unstated package installations

## Maintainer-Side Review Flow

When a collaborator submits a workflow candidate, the maintainer should perform these checks:

1. validate the standard onboarding bundle
2. validate the workflow-candidate schema files
3. inspect the entrypoint contract
4. run the smoke test
5. confirm the intermediate outputs match the declared format
6. run the standard extractor stage if applicable
7. compare the resulting GMTs to the collaborator-submitted reference GMTs
8. decide whether to:
   - reject
   - keep as hybrid only
   - promote into a canonical workflow archetype

## Promotion Criteria

A workflow candidate should only be promoted if it is:

- structurally clear
- reusable beyond one exact dataset
- compatible with the branch output standards
- provenance-complete
- understandable by the maintainer
- reproducible under an approved environment

## What Promotion Would Mean

If promoted, the maintainer would:

1. create a canonical `WORKFLOW_ARCHETYPES` entry
2. adapt the candidate implementation into the standard generator code
3. add validation hooks to `library_onboard.py`
4. add maintainer review rules to `review_submission_archive.py`
5. document the new workflow archetype in the collaborator docs

## Why This Is Better Than Full Fork Submission

Compared with the current repo-fork pattern, this proposal gives the maintainer:

- a clear workflow boundary
- a fixed CLI contract
- explicit input and output expectations
- explicit provenance expectations
- a reusable promotion path

It gives the collaborator:

- a structured way to submit a new workflow
- a way to explain why the workflow exists
- a way to preserve output fidelity without requiring exact code integration up front

## Recommended First Use Case

The best first example is exactly the kind of case Trang represents:

- a custom workflow such as `igvf_perturbseq`
- a final extractor that already exists (`signed_term_gene`)
- a strong need to reproduce the same GMTs

That is the ideal scenario for a workflow-candidate submission format.

## Recommendation

Yes, collaborators should be allowed to submit workflow archetype candidates.

But they should do so through a **strict workflow-candidate bundle contract**, not as arbitrary repo forks.

The maintainer should then decide whether the candidate becomes:

- a one-off `custom_hybrid`
- or a new canonical reusable workflow archetype

That gives you the flexibility to ingest workflows like Trang's while keeping the branch maintainable.
