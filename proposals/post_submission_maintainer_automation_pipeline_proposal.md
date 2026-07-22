# Post-Submission Maintainer Automation Pipeline Proposal

## Goal

Define a maintainer-side automation pipeline for collaborator submission archives produced by the single-interaction template-driven library generator workflow.

The automation should reduce manual review burden while preserving human control over:

- final publishability decisions
- canonical promotion decisions
- scientific appropriateness decisions

## Why This Is Needed

Once collaborators begin returning full submission archives, the bottleneck moves from collaborator guidance to maintainer intake and review.

Without automation, the maintainer still has to repeatedly do the following by hand:

- unpack submission archives
- inspect manifests
- verify output structure
- check metadata and provenance for local path leakage
- confirm archetype compatibility
- summarize readiness

Those steps are repetitive and are good candidates for automation.

## Core Principle

The automation pipeline should:

- automate evidence gathering
- automate conformance checks
- automate summary generation

It should **not** automatically make irreversible acceptance decisions.

Instead, it should produce a structured review package that supports a human maintainer decision.

## Proposed Automation Scope

### Fully automatable stages

- submission intake
- archive unpacking
- structural validation
- archetype conformance validation
- metadata/provenance checks
- GMT checks
- summary report generation

### Partially automatable stages

- representative reruns
- canonical scaffold staging
- artifact repair

### Human-only decision stages

- final publishability approval
- canonical maintenance approval
- scientific appropriateness review

## Proposed Pipeline Stages

### Stage 1: Intake submission

Input:

- one collaborator submission archive

Actions:

- unpack archive
- identify root structure
- locate generated package
- locate output tree
- locate manifests

Outputs:

- normalized intake directory
- `intake_summary.json`
- `intake_summary.md`

### Stage 2: Validate archive structure

Checks:

- required top-level directories exist
- generated package code is present
- expected config files are present
- expected run scripts are present
- expected output tree exists

Outputs:

- `structure_report.json`
- `structure_report.md`

### Stage 3: Validate archetype conformance

Checks:

- claimed archetype is present
- generated package matches the expected template family
- expected DIG converter or workflow command is used
- required config keys for the archetype are present
- model and partition records are internally consistent

Outputs:

- `archetype_report.json`
- `archetype_report.md`

### Stage 4: Validate output artifacts

Checks:

- GMT files exist
- metadata JSON files exist
- provenance JSON files exist
- model sidecars exist
- `.orig` files exist where expected

Outputs:

- `artifact_report.json`
- `artifact_report.md`

### Stage 5: Validate metadata and provenance

Checks:

- no collaborator-local filesystem paths remain
- metadata descriptions are populated
- provenance descriptions are populated
- metadata and provenance descriptions agree
- provenance includes the expected command chain for the archetype
- external inputs are represented as stable URIs or URLs

Outputs:

- `provenance_report.json`
- `provenance_report.md`

### Stage 6: Validate GMTs

Checks:

- GMT files are parseable
- second-column descriptions are populated
- naming pattern matches archetype expectations
- signed libraries use `up` / `dn` consistently

Outputs:

- `gmt_report.json`
- `gmt_report.md`

### Stage 7: Compute publishability status

The pipeline should map validation results into a recommendation:

- `ready`
- `ready_with_minor_repairs`
- `not_ready`

This is only a recommendation, not a final decision.

Outputs:

- `publishability_summary.json`
- `publishability_summary.md`

## Optional Later Stages

### Stage 8: Representative rerun

This stage is partially automatable.

Actions:

- pick one partition/model pair
- rerun under the maintainer environment
- compare output presence and basic structure

Possible outputs:

- `rerun_report.json`
- `rerun_report.md`

### Stage 9: Canonical scaffold staging

This stage prepares a candidate canonical library tree:

- `geneset-extractor-dev/<Library>/config/`
- `geneset-extractor-dev/<Library>/planning/`
- `geneset-extractor-dev/<Library>/run/`
- `geneset-extractor-dev/<Library>/src/`

This should be a staged suggestion, not an automatic acceptance.

Possible outputs:

- staged canonical tree
- `canonicalization_report.md`

### Stage 10: Artifact repair

Optional maintainer-side repair stage:

- refresh metadata
- refresh provenance
- rewrite paths
- regenerate GMT descriptions

This can be automated as a repair candidate, but should still be reviewed before publication.

## Proposed Tooling

### Main entrypoint

Suggested new tool:

- `geneset-extractor-dev/src/review_submission_archive.py`

Suggested wrapper:

- `geneset-extractor-dev/run/review_submission_archive.sh`

### Optional later tools

- `rerun_submission_sample.py`
- `stage_submission_as_canonical_library.py`
- `repair_submission_artifacts.py`

## Proposed CLI

### Intake and validation

```bash
bash geneset-extractor-dev/run/review_submission_archive.sh \
  --submission_zip /path/to/submission.zip \
  --review_root /path/to/reviews/submission_name
```

This should:

- unpack the archive
- run all non-destructive validation stages
- write a review bundle

### Optional representative rerun

```bash
bash geneset-extractor-dev/run/rerun_submission_sample.sh \
  --review_root /path/to/reviews/submission_name \
  --dig_dir /path/to/dig-gene-set-extractors \
  --apptainer_image /path/to/geneset-extractor.sif
```

### Optional canonical staging

```bash
bash geneset-extractor-dev/run/stage_submission_as_canonical_library.sh \
  --review_root /path/to/reviews/submission_name \
  --extractor_root /path/to/geneset-extractor-dev
```

## Proposed Review Output Layout

For each submission, the automation pipeline should produce a review directory like:

```text
reviews/<submission_name>/
  unpacked_submission/
  reports/
    intake_summary.json
    intake_summary.md
    structure_report.json
    structure_report.md
    archetype_report.json
    archetype_report.md
    artifact_report.json
    artifact_report.md
    provenance_report.json
    provenance_report.md
    gmt_report.json
    gmt_report.md
    publishability_summary.json
    publishability_summary.md
  staging/
    <optional canonical scaffold>
```

## Validation Rules

### Archive structure rules

- submission archive must unpack successfully
- generated package must exist
- `config/`, `src/`, `run/`, and output tree must be present

### Archetype rules

- claimed archetype must be supported
- generated package must match the expected archetype template
- required options must be present

### Artifact rules

- final output directories must exist
- each expected model/partition combination must contain required sidecars

### Metadata and provenance rules

- no local `/home/`, `/Users/`, or `/humgen/` paths in final publish-facing metadata/provenance
- provenance command chain must be present
- external inputs must be represented in a stable way

### GMT rules

- file must be parseable
- description column must be populated
- naming must be consistent

## Recommendation Logic

The pipeline should classify findings into severity tiers.

### Critical

Examples:

- missing provenance
- missing metadata
- local path leakage
- archetype mismatch
- no GMTs generated

Critical findings should force:

- `not_ready`

### Major

Examples:

- incomplete `.orig` preservation
- missing model sidecars
- inconsistent descriptions
- missing expected output subset

Major findings should usually force:

- `ready_with_minor_repairs`
or
- `not_ready`

depending on count and context.

### Minor

Examples:

- wording inconsistencies
- missing optional notes
- cosmetic naming issues

Minor findings can still be:

- `ready`
or
- `ready_with_minor_repairs`

## Human Decision Point

After the automation finishes, the maintainer reviews the generated reports and then decides:

- accept for publication and canonical onboarding
- accept for publication only
- accept pending maintainer-side repair
- reject as submitted

That final decision should remain manual.

## Recommended First Implementation

The first version should stop after:

- intake
- structure validation
- archetype validation
- artifact validation
- metadata/provenance validation
- GMT validation
- publishability summary generation

This gives immediate value without requiring rerun or canonical staging automation on day one.

## Recommended Second Implementation

After the first version is stable, add:

- representative rerun automation
- canonical scaffold staging

## Recommended Third Implementation

Later, add:

- artifact repair automation
- optional publish upload preparation

## Relationship To Existing Libraries

This automation pipeline should be implemented as a new subsystem and should not disturb:

- GTEx
- MoTrPAC
- HuBMAP
- LINCS_L1000

It should operate on returned collaborator submission archives, not on the existing canonical library codepaths.

## Bottom Line

Yes, the post-submission maintainer workflow can be automated substantially.

The correct design is a staged review pipeline that automates:

- archive intake
- conformance checks
- output validation
- publishability summary generation

while keeping final acceptance and canonical promotion as human maintainer decisions.
