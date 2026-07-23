# Workflow-Archetype Schema Proposal

## Goal

Extend the automated collaborator onboarding system so it can represent libraries shaped like:

- `GTEx`
- `MoTrPAC`
- `LINCS_L1000`
- `HuBMAP`
- future environment-special cases such as `LIGER`

The current onboarding system is centered on **extractor archetypes**:

- `released_de_rna`
- `unsigned_term_gene`
- `signed_term_gene`

That is too narrow for real libraries, because those libraries are usually:

1. raw or released inputs
2. one or more workflow/preparation steps
3. one DIG converter step
4. metadata/provenance refresh
5. validation and packaging

The system therefore needs a new **workflow archetype** layer above the current converter archetypes.

## Core Model

Each onboarded library should be described by two related concepts:

1. `workflow_archetype`
2. `extractor_archetype`

### Workflow archetype

Describes:

- input shapes
- partitioning rules
- model-family behavior
- workflow command templates
- expected intermediate files
- supported environment profile

### Extractor archetype

Describes:

- final DIG converter
- required converter options
- output naming and sidecars

The extractor archetype remains useful, but it is no longer the top-level abstraction.

## Proposed Workflow Archetypes

The first useful set should directly reflect the existing canonical libraries.

### 1. `bulk_counts_multi_model`

Inspired by:

- `GTEx`

Input shape:

- counts matrix
- sample metadata
- phenotype/subject metadata
- optional annotations such as gene info or GTF

Common behavior:

- library partitions are tissues or comparable biological subsets
- one partition can be run under several model families
- workflow emits DE or ranked outputs per model/partition
- extractor stage may be repeated per comparison

Typical model families:

- age-binned models
- continuous models
- notebook-faithful/reference-matched models

### 2. `released_de_multi_partition`

Inspired by:

- `MoTrPAC` released DEA-style models
- collaborator libraries built from released differential-expression tables

Input shape:

- one released DE table per partition
- metadata describing tissue, contrast, or grouping

Common behavior:

- partition-specific released inputs
- minimal statistical recomputation
- mostly a preparation and naming workflow before conversion

### 3. `raw_counts_training_timecourse`

Inspired by:

- `MoTrPAC` raw-count workflows

Input shape:

- raw counts
- sample metadata
- phenotype metadata
- annotation/mapping files

Common behavior:

- workflow computes contrasts from raw inputs
- model families differ by grouping strategy and covariates
- outputs can feed `signed_term_gene`

### 4. `matrix_signature_library`

Inspired by:

- `LINCS_L1000`

Input shape:

- perturbation or gene-signature matrix
- feature/ID mapping file

Common behavior:

- workflow reshapes matrix into signed term-gene form
- often one global partition such as `all_signatures`
- models distinguish matrix semantics, not tissue partitions

### 5. `table_directory_marker_library`

Inspired by:

- `HuBMAP`

Input shape:

- directory of source tables
- optional gene-info or annotation files

Common behavior:

- workflow merges or normalizes many source tables
- workflow emits one unsigned term-gene table
- converter creates the final library

### 6. `custom_hybrid`

Fallback for libraries that still do not fit a fully declarative workflow archetype.

Use cases:

- new DIG workflow needed
- novel extraction semantics
- unsupported environment

This mode should still produce a standard bundle, but should explicitly mark the library as requiring maintainer-side implementation or approval.

## Proposed Schema Changes

The collaborator bundle should move from a converter-centric schema to a library-centric one.

### Current files that remain useful

- `bundle_manifest.json`
- `library_config.json`
- `inputs_manifest.tsv`
- `partition_list.tsv`
- `model_list.tsv`
- `model_manifest.tsv`
- `model_description_templates.tsv`

### New or expanded top-level fields in `library_config.json`

```json
{
  "library_name": "GTEx",
  "library_slug": "GTEx",
  "workflow_archetype": "bulk_counts_multi_model",
  "extractor_archetype": "released_de_rna",
  "source_project": "GTEx",
  "assay_type": "bulk_rna_seq",
  "data_type": "gene_expression",
  "organism": "human",
  "genome_build": "hg38",
  "input_granularity": "counts_plus_metadata",
  "output_granularity": "partition_model_or_comparison",
  "signed_output": "true",
  "natural_parallel_unit": "tissue_model",
  "environment_profile": "geneset_extractor_standard",
  "expected_workflow_category": "bulk_counts_multi_model",
  "notes": ""
}
```

### New `workflow_manifest.json`

This should declare the workflow-level behavior explicitly.

Suggested shape:

```json
{
  "workflow_archetype": "bulk_counts_multi_model",
  "entrypoint_template": "src/build_<library_slug>_genesets.py",
  "partition_axis": "tissue",
  "comparison_axis": "model_specific",
  "emits_intermediate_tables": true,
  "intermediate_file_roles": [
    "de_tsv",
    "signed_term_gene_tsv",
    "unsigned_term_gene_tsv"
  ],
  "requires_refresh": true,
  "supports_apptainer": true,
  "environment_profile": "geneset_extractor_standard"
}
```

### New `environment_profile.json`

This file should declare what runtime the generated package expects.

Suggested values:

- `geneset_extractor_standard`
- `geneset_extractor_r_heavy`
- `maintainer_only`
- `custom_approved_image`

Suggested shape:

```json
{
  "environment_profile": "geneset_extractor_standard",
  "apptainer_image_required": true,
  "python_required": true,
  "r_required": false,
  "allowed_wrapper_modes": [
    "direct",
    "apptainer",
    "cluster_apptainer"
  ],
  "notes": ""
}
```

## Inputs Manifest Updates

The current `inputs_manifest.tsv` should gain fields that distinguish workflow-level and extractor-level inputs.

Suggested headers:

- `input_id`
- `path_or_uri`
- `input_role`
- `workflow_stage`
- `format`
- `is_external_input`
- `required_for_rerun`
- `source_url_or_uri`
- `partition_scope`
- `notes`

Example `workflow_stage` values:

- `workflow_input`
- `extractor_input`
- `annotation_input`

## Partition Manifest Updates

The current `partition_list.tsv` should become more explicit about the natural parallel axis.

Suggested headers:

- `partition_id`
- `partition_label`
- `partition_type`
- `partition_group`
- `input_id`
- `enabled`
- `notes`

Examples:

- GTEx tissue
- MoTrPAC tissue
- HuBMAP all_signatures
- LINCS all_signatures

## Model Manifest Updates

The current model manifests should be extended so model families are declarative rather than mostly free-form.

Suggested fields:

- `model_id`
- `model_family`
- `model_label`
- `workflow_variant`
- `extractor_archetype`
- `signed_output`
- `comparison_style`
- `distinct_algorithmic_feature`
- `options_json`
- `enabled`

Examples:

- GTEx `AB1`, `AC1`, `HZ1`
- MoTrPAC `TR1`, `TW1`, `HZ1`
- LINCS `HZ1`, `HZ2`
- HuBMAP `HZ1`, `HZ2`

## Naming Contract

Each workflow archetype should expose naming variables that user-facing templates can rely on.

Required naming variables should include:

- `signature_name`
- `partition_label`
- `comparison_label`
- `comparison_description`
- `reference_label`
- `contrast_label`
- `sex_label`
- `timepoint_label`
- `term_prefix`

These variables should be populated into:

- `geneset.model.json`
- `geneset.meta.json`
- `geneset.provenance.json`
- GMT second-column descriptions

This prevents each library from inventing naming logic ad hoc.

## Description Contract

Each workflow archetype should require:

1. model-level description template
2. gene-set-level description template
3. GMT-row description template

The system should stop treating descriptions as a post hoc patch. They should be part of the archetype contract.

## Provenance Contract

Each workflow archetype must define:

- the minimum command chain expected in provenance
- the required external inputs for rerun
- which intermediate files are expected to appear as file nodes
- whether a workflow directory argument must be sanitized to a generic path

Examples:

- `table_directory_marker_library` should allow directory inputs such as `raw_asctb_dir`
- `matrix_signature_library` should preserve mapping files and matrix inputs
- `bulk_counts_multi_model` should preserve counts, metadata, and annotation inputs

## Output Contract

Every archetype-generated package should still emit the same standard publishable outputs:

- `genesets.gmt`
- `geneset.meta.json`
- `geneset.provenance.json`
- `geneset.model.json`
- `.orig` copies where refresh rewrites files

Optional outputs may vary, but those should remain mandatory.

## Compatibility With Existing Libraries

This schema is designed to represent the current five library patterns without forcing each one into a fake converter-only abstraction.

### GTEx

- `workflow_archetype = bulk_counts_multi_model`
- `extractor_archetype = released_de_rna`

### MoTrPAC

- `workflow_archetype = released_de_multi_partition` or `raw_counts_training_timecourse`
- `extractor_archetype = signed_term_gene`

### LINCS_L1000

- `workflow_archetype = matrix_signature_library`
- `extractor_archetype = signed_term_gene`

### HuBMAP

- `workflow_archetype = table_directory_marker_library`
- `extractor_archetype = unsigned_term_gene`

### LIGER-like future cases

- likely `custom_hybrid` initially
- later promotable into a dedicated workflow archetype if repeated enough

## Recommendation

The automated system should preserve the current extractor archetypes, but treat them as the final stage of a broader workflow model.

The new top-level schema should be driven by:

- `workflow_archetype`
- `extractor_archetype`
- `environment_profile`
- declarative model-family behavior
- explicit naming and provenance contracts

That is the minimum structure needed to onboard future libraries that actually resemble the existing maintained codebase.
