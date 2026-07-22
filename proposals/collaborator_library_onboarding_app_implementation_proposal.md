# Collaborator Library Onboarding App Implementation Proposal

## Goal

Define a concrete first implementation for a collaborator-facing onboarding app that:

- runs locally on a collaborator machine
- does not require Git knowledge
- captures the information needed to onboard a new library
- emits a standardized zip bundle
- supports maintainer-side validation and scaffold generation

This proposal is the implementation follow-up to:

- `collaborator_library_onboarding_workflow_proposal.md`
- `collaborator_library_scaffold_app_proposal.md`

## Recommended First Version

Build a **CLI-first onboarding app** with two user roles:

- **collaborator mode**
- **maintainer mode**

The collaborator mode creates a structured onboarding bundle.

The maintainer mode validates that bundle and generates a draft scaffold under the canonical `geneset-extractor-dev` tree.

## Why CLI First

A CLI is the right first version because it is:

- easier to distribute
- easier to run on Linux and cluster-adjacent systems
- easier to version-control internally
- easier to test automatically
- lower maintenance than a local web app

A GUI or local web app can be added later if needed.

## Proposed Tool Name

Suggested internal name:

- `library_onboard`

Possible command form:

```bash
python -m library_onboard <subcommand> [options]
```

or with a thin wrapper:

```bash
bash geneset-extractor-dev/run/library_onboard.sh <subcommand> [options]
```

## Proposed Repository Placement

Recommended location for the first version:

- `geneset-extractor-dev/src/library_onboard.py`

If the tool grows, it can later move to:

- `geneset-extractor-dev/src/library_onboard/`

with multiple modules.

## Collaborator-Facing CLI

### 1. Initialize a bundle workspace

```bash
python -m library_onboard init \
  --library_name MyLibrary \
  --out_dir ./MyLibrary_onboarding
```

Creates:

- bundle directory
- starter JSON/TSV/Markdown files
- schema version marker

### 2. Guided questionnaire

```bash
python -m library_onboard questionnaire \
  --bundle_dir ./MyLibrary_onboarding
```

Prompts for:

- library identity
- assay type
- organism
- genome build
- high-level workflow type
- natural partitions
- expected model count

### 3. Add inputs

```bash
python -m library_onboard add_input \
  --bundle_dir ./MyLibrary_onboarding
```

Prompts for one input at a time:

- local path or remote URL/URI
- input role
- file type
- required for rerun: yes/no
- notes

### 4. Add partitions

```bash
python -m library_onboard add_partition \
  --bundle_dir ./MyLibrary_onboarding
```

Prompts for:

- partition ID
- partition label
- partition type
- expected input subset
- expected output unit

### 5. Add models

```bash
python -m library_onboard add_model \
  --bundle_dir ./MyLibrary_onboarding
```

Prompts for:

- model ID
- model family
- short description
- distinct algorithmic behavior
- input mode
- signed or unsigned
- expected gene set naming pattern

### 6. Validate

```bash
python -m library_onboard validate \
  --bundle_dir ./MyLibrary_onboarding
```

Checks:

- required files exist
- required fields are populated
- IDs are unique
- enumerated values are valid
- partition and model records are internally consistent

### 7. Package

```bash
python -m library_onboard package \
  --bundle_dir ./MyLibrary_onboarding \
  --out_zip ./MyLibrary_onboarding_bundle.zip
```

Produces:

- zipped onboarding bundle
- summary manifest

## Maintainer-Facing CLI

### 1. Inspect bundle

```bash
python -m library_onboard inspect \
  --bundle_zip ./MyLibrary_onboarding_bundle.zip
```

Outputs:

- library summary
- input inventory summary
- partition summary
- model summary
- validation status

### 2. Validate bundle

```bash
python -m library_onboard validate_bundle \
  --bundle_zip ./MyLibrary_onboarding_bundle.zip
```

Checks:

- same schema checks as collaborator-side validate
- zip contains the required structure
- no malformed tables

### 3. Generate canonical scaffold

```bash
python -m library_onboard scaffold \
  --bundle_zip ./MyLibrary_onboarding_bundle.zip \
  --extractor_root /path/to/geneset-extractor-dev \
  --library_name MyLibrary
```

Generates a draft:

- `geneset-extractor-dev/<Library>/config/`
- `geneset-extractor-dev/<Library>/planning/`
- `geneset-extractor-dev/<Library>/run/`
- `geneset-extractor-dev/<Library>/src/`

## Bundle File Format

### Required files

Recommended minimum bundle layout:

```text
<library_name>_onboarding/
  bundle_manifest.json
  library_manifest.json
  inputs_manifest.tsv
  partition_plan.tsv
  model_plan.tsv
  questionnaire.json
  run_examples.md
  notes.md
```

### Optional files

- `sample_inputs/`
- `sample_outputs/`
- `references/`
- `data_dictionary.tsv`

## Proposed File Schemas

### `bundle_manifest.json`

Purpose:

- top-level metadata for the onboarding bundle

Suggested fields:

- `schema_version`
- `bundle_created_at`
- `library_name`
- `collaborator_name`
- `contact_email`
- `bundle_tool_version`
- `contains_sample_inputs`
- `contains_sample_outputs`

### `library_manifest.json`

Purpose:

- high-level library identity and workflow intent

Suggested fields:

- `library_name`
- `source_project`
- `assay_type`
- `data_type`
- `organism`
- `genome_build`
- `input_granularity`
- `output_granularity`
- `signed_output`
- `natural_parallel_unit`
- `expected_workflow_category`
- `notes`

### `inputs_manifest.tsv`

Suggested columns:

- `input_id`
- `path_or_uri`
- `input_role`
- `format`
- `is_external_input`
- `required_for_rerun`
- `source_url_or_uri`
- `notes`

### `partition_plan.tsv`

Suggested columns:

- `partition_id`
- `partition_label`
- `partition_type`
- `enabled`
- `notes`

### `model_plan.tsv`

Suggested columns:

- `model_id`
- `model_family`
- `model_label`
- `input_mode`
- `signed_output`
- `gene_set_pattern`
- `distinct_algorithmic_feature`
- `description`
- `enabled`

### `questionnaire.json`

Purpose:

- preserve the collaborator’s high-level answers from the guided intake

This is useful because it captures intent beyond normalized TSVs.

## Maintainer Scaffold Output

Given a validated bundle, the scaffold command should generate:

```text
geneset-extractor-dev/<Library>/
  config/
    model_list.tsv
    model_manifest.tsv
    model_description_templates.tsv
    partition_list.tsv
  planning/
    pipeline_inputs.md
    onboarding_summary.md
    implementation_notes.md
  run/
    build_<library>_genesets.sh
    refresh_<library>_metadata_and_provenance.sh
  src/
    build_<library>_genesets.py
    run_<library>_model.py
```

The generated files should be explicit placeholders, not fake finished implementations.

## Validation Rules

### Required first-version rules

1. `library_name` must be present
2. `organism` must be present
3. at least one external input must be recorded
4. at least one model must be defined
5. model IDs must be unique
6. partition IDs must be unique
7. if `signed_output=true`, the naming pattern must allow directional labels
8. every required input must have either a local path or a source URI

### Recommended warning-only rules

1. no sample inputs attached
2. no sample output examples attached
3. no run examples provided
4. model descriptions are too vague

## Proposed Development Phases

### Phase 1: bundle generator

Implement:

- `init`
- `questionnaire`
- `add_input`
- `add_partition`
- `add_model`
- `validate`
- `package`

Output:

- valid onboarding zip bundle

### Phase 2: maintainer tooling

Implement:

- `inspect`
- `validate_bundle`
- `scaffold`

Output:

- generated draft library scaffold in canonical tree

### Phase 3: polish

Add:

- better prompt UX
- TSV import helpers
- noninteractive batch mode
- templated summary docs

### Phase 4: optional portal integration

Later, if a central portal exists:

- allow direct bundle upload
- assign intake IDs
- track status of review and integration

## Noninteractive Mode

The app should eventually support both:

- interactive prompt mode
- noninteractive file-driven mode

Example:

```bash
python -m library_onboard import_inputs \
  --bundle_dir ./MyLibrary_onboarding \
  --inputs_tsv ./my_inputs.tsv
```

This matters because some collaborators may already maintain structured tables.

## Apptainer Considerations

The onboarding app itself does not need Apptainer.

It only writes bundle metadata and scaffold files.

However, the scaffold generator should emit planning notes that explicitly reserve places for:

- apptainer execution commands
- cluster submission commands
- refresh metadata/provenance commands

That way the generated scaffold is compatible with the way the four canonical libraries are already run.

## Risks

### Risk 1: Too much required metadata

If the intake is too detailed, collaborators may stall.

Mitigation:

- required minimum fields first
- optional detail fields later

### Risk 2: Auto-generated scaffold appears more complete than it is

Mitigation:

- generated files should contain explicit placeholder comments
- scaffold should be clearly marked as draft

### Risk 3: Maintainer still has to reinterpret free text

Mitigation:

- prefer structured TSV/JSON fields over long-form prose wherever possible

## Recommendation

Build Phase 1 and Phase 2 first.

That will be enough to:

- eliminate Git as a collaborator requirement
- standardize what new-library collaborators submit
- reduce submission ambiguity
- create a cleaner path into canonical integration

## Bottom Line

The best concrete next step is a CLI onboarding app that produces a structured bundle and a maintainer-side scaffold generator that turns that bundle into a draft canonical library tree.

That approach is realistic, incremental, and compatible with the architecture already established by GTEx, MoTrPAC, HuBMAP, and LINCS_L1000.
