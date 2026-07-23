# Single-Interaction Template Generator Collaborator Guide

## Purpose

This guide explains how a collaborator can use the template-driven `library_onboard` tool to:

- describe a new library once
- generate a runnable library package locally
- run the package
- validate the outputs
- send back one final archive containing code, GMT files, metadata, and provenance

This workflow is intended for **template-compatible libraries** only.

## Recommended Starting Point

If you are starting from a dataset and do not yet know which onboarding path fits, read the quickstart first:

- `geneset-extractor-dev/docs/dev/add_new_library/collaborator_onboarding_quickstart.md`

That document explains:

1. how to inspect the supported workflow archetypes
2. how to inspect the supported extractor archetypes
3. how to inspect the supported environment profiles
4. how to choose the best matching workflow shape
5. how to run the first `init` command

The short version is:

```bash
bash geneset-extractor-dev/run/library_onboard.sh list-workflow-archetypes
bash geneset-extractor-dev/run/library_onboard.sh list-archetypes
bash geneset-extractor-dev/run/library_onboard.sh list-environment-profiles
```

Then choose the closest match and initialize a bundle like this:

```bash
bash geneset-extractor-dev/run/library_onboard.sh init \
  --library_name MyLibrary \
  --out_dir ./MyLibrary_onboarding \
  --archetype unsigned_term_gene \
  --workflow_archetype table_directory_marker_library \
  --environment_profile geneset_extractor_standard
```

## Important Limitation

This process only works for libraries that fit an already supported archetype.

Examples of currently supported extractor archetypes:

- released differential-expression table -> `rna_deg`
- unsigned term-gene table -> `unsigned_term_gene`
- signed term-gene table -> `signed_term_gene`

Examples of currently supported workflow archetypes:

- `simple_converter`
- `released_de_multi_partition`
- `bulk_counts_multi_model`
- `raw_counts_training_timecourse`
- `matrix_signature_library`
- `table_directory_marker_library`
- `custom_hybrid`

If your library requires:

- a brand-new DIG workflow
- a brand-new DIG converter
- nonstandard extraction logic

then this one-shot workflow is not appropriate. In that case, the onboarding bundle can still be created, but the maintainer will need to implement the runnable library code separately.

## What You Receive

To follow this workflow, you should receive:

- the `geneset-extractor-dev` onboarding tool files
- access to your library input data
- optionally a `geneset-extractor` Apptainer image
- optionally a local checkout of `dig-gene-set-extractors`

The onboarding tool is currently run from:

- `geneset-extractor-dev/run/library_onboard.sh`
- `geneset-extractor-dev/src/library_onboard.py`

## Overview Of The Workflow

The process has eight steps:

1. inspect the supported workflow, extractor, and environment options
2. initialize an onboarding bundle
3. record the library inputs
4. define partitions and models
5. validate the bundle
6. generate a runnable package
7. run the package locally or with Apptainer
8. validate the outputs
9. package the final submission and send it back

## 1. Inspect The Supported Options

Before creating a bundle, determine which workflow shape best matches your data.

Run:

```bash
bash geneset-extractor-dev/run/library_onboard.sh list-workflow-archetypes
bash geneset-extractor-dev/run/library_onboard.sh list-archetypes
bash geneset-extractor-dev/run/library_onboard.sh list-environment-profiles
```

At this stage, decide:

1. the `workflow_archetype`
2. the final extractor archetype
3. the environment profile

Common examples:

- directory of marker tables:
  `workflow_archetype = table_directory_marker_library`
  `extractor_archetype = unsigned_term_gene`
- signature matrix:
  `workflow_archetype = matrix_signature_library`
  `extractor_archetype = signed_term_gene`
- released differential-expression tables:
  `workflow_archetype = released_de_multi_partition`
  `extractor_archetype = released_de_rna`
- counts plus metadata:
  `workflow_archetype = bulk_counts_multi_model`
  `extractor_archetype = released_de_rna`

## 2. Initialize An Onboarding Bundle

Choose a supported workflow and extractor combination and create a bundle directory.

Example:

```bash
bash geneset-extractor-dev/run/library_onboard.sh init \
  --library_name MyLibrary \
  --out_dir ./MyLibrary_onboarding \
  --archetype unsigned_term_gene \
  --workflow_archetype table_directory_marker_library \
  --environment_profile geneset_extractor_standard
```

This creates:

- `bundle_manifest.json`
- `library_manifest.json`
- `inputs_manifest.tsv`
- `partition_plan.tsv`
- `model_plan.tsv`
- `questionnaire.json`
- `run_examples.md`
- `notes.md`

## 3. Record The Library Inputs

Add each required external input.

Example:

```bash
bash geneset-extractor-dev/run/library_onboard.sh add-input \
  --bundle_dir ./MyLibrary_onboarding \
  --input_id main_table \
  --path_or_uri /path/to/local/input.tsv \
  --input_role table_tsv \
  --workflow_stage workflow_input \
  --format tsv \
  --is_external_input true \
  --required_for_rerun true \
  --source_url_or_uri https://example.org/input.tsv
```

Key points:

- `path_or_uri` is your local working path
- `source_url_or_uri` is the stable external source URI or URL that should appear in final provenance
- every input required for rerunning the analysis should be recorded

## 4. Define Partitions And Models

### Add partitions

If your library is split by study, dataset, tissue, contrast, or another natural unit, add one partition per row.

Example:

```bash
bash geneset-extractor-dev/run/library_onboard.sh add-partition \
  --bundle_dir ./MyLibrary_onboarding \
  --partition_id StudyA \
  --partition_label StudyA \
  --partition_type study \
  --partition_group primary \
  --input_id main_table
```

### Add models

Add one or more models that describe the analysis variants you want to run.

Example:

```bash
bash geneset-extractor-dev/run/library_onboard.sh add-model \
  --bundle_dir ./MyLibrary_onboarding \
  --model_id U1 \
  --model_family unsigned_term_gene \
  --model_label canonical \
  --input_mode released_table \
  --workflow_variant default \
  --extractor_archetype unsigned_term_gene \
  --signed_output false \
  --gene_set_pattern 'MyLibrary_<term>' \
  --comparison_style library \
  --distinct_algorithmic_feature 'unsigned conversion' \
  --description 'MyLibrary unsigned term-gene library using model U1.' \
  --options_json '{"term_column":"term","gene_id_column":"gene_id","gene_symbol_column":"gene_symbol","score_column":"score","term_prefix":"MyLibrary"}'
```

### Optional questionnaire metadata

You can also record higher-level context:

```bash
bash geneset-extractor-dev/run/library_onboard.sh questionnaire \
  --bundle_dir ./MyLibrary_onboarding \
  --set library_identity.owner='collaborator_name' \
  --set workflow_shape.parallel_unit='partition'
```

## 5. Validate The Bundle

Before generating code, validate the bundle:

```bash
bash geneset-extractor-dev/run/library_onboard.sh validate \
  --bundle_dir ./MyLibrary_onboarding
```

This checks:

- required files exist
- `library_manifest.json` is populated
- inputs are recorded
- partitions exist
- models exist
- IDs are unique
- the selected archetype is supported

If validation fails, fix the bundle first.

## 6. Generate A Runnable Package

If the library is template-compatible, generate the runnable package:

```bash
bash geneset-extractor-dev/run/library_onboard.sh generate-package \
  --bundle_dir ./MyLibrary_onboarding \
  --out_dir ./MyLibrary_package
```

This creates a generated package with:

- `config/`
- `src/`
- `run/`
- `planning/`
- `README.md`

The generated package contains:

- build scripts
- per-model runner logic
- validation logic
- packaging scripts
- Apptainer run wrapper

## 7. Run The Generated Package

From this point on, you work from the generated package.

### Local run

Example:

```bash
bash run/build_MyLibrary_genesets.sh \
  --dig_dir /path/to/dig-gene-set-extractors \
  --out_root ./outputs/MyLibrary_all_models
```

### Apptainer run

If you prefer Apptainer:

```bash
export APPTAINER_IMAGE=/path/to/geneset-extractor.sif
export DIG_DIR=/path/to/dig-gene-set-extractors
bash run/build_MyLibrary_genesets_apptainer.sh
```

The generated package will:

- read the generated configs
- iterate over partitions and models
- call the corresponding DIG converter command
- write outputs to a standard output tree

## 7. What Gets Written During The Run

For each partition/model combination, the generated package writes a standard output tree under:

```text
outputs/<library_slug>_all_models/
  genesets/<partition_id>/models/<model_id>/
```

The generated runner also attempts to finalize the outputs so they are closer to publish-ready:

- writes `geneset.model.json`
- populates GMT second-column descriptions
- updates `geneset.meta.json`
- updates `geneset.provenance.json`
- preserves `.orig` files on first rewrite
- replaces local output-root paths with the configured mirror URI
- replaces local input paths with the stable `source_url_or_uri` values from the onboarding bundle

## 8. Validate The Outputs

After the run finishes, validate the outputs:

```bash
bash run/validate_MyLibrary_outputs.sh
```

This checks:

- GMT files exist
- metadata exists
- provenance exists
- model sidecars exist
- no local `/home/`, `/Users/`, or `/humgen/` paths remain in final metadata or provenance
- GMT second-column descriptions are populated

If validation fails, fix the bundle or rerun the package before packaging the final submission.

## 9. Package The Final Submission

Once validation passes, create the final archive:

```bash
bash run/package_submission.sh
```

This packages:

- generated code
- configs
- planning docs
- output tree
- logs
- metadata
- provenance
- GMT files

The result should be one submission archive that you can return to the maintainer.

## 10. What You Send Back

The final submission should contain:

- the generated library package
- the generated outputs
- logs
- metadata and provenance
- GMT files

This is intended to be a single return package rather than a forked codebase plus separate output tree.

## Recommended Working Pattern

Use this order:

1. initialize the bundle
2. add inputs
3. add partitions
4. add models
5. validate the bundle
6. generate the package
7. run the package
8. validate the outputs
9. package the submission

## Example Minimal Workflow

```bash
bash geneset-extractor-dev/run/library_onboard.sh init \
  --library_name MyLibrary \
  --out_dir ./MyLibrary_onboarding \
  --archetype unsigned_term_gene

bash geneset-extractor-dev/run/library_onboard.sh add-input \
  --bundle_dir ./MyLibrary_onboarding \
  --input_id main_table \
  --path_or_uri /path/to/local/input.tsv \
  --input_role table_tsv \
  --format tsv \
  --is_external_input true \
  --required_for_rerun true \
  --source_url_or_uri https://example.org/input.tsv

bash geneset-extractor-dev/run/library_onboard.sh add-partition \
  --bundle_dir ./MyLibrary_onboarding \
  --partition_id all_signatures \
  --partition_label AllSignatures \
  --partition_type global \
  --input_id main_table

bash geneset-extractor-dev/run/library_onboard.sh add-model \
  --bundle_dir ./MyLibrary_onboarding \
  --model_id U1 \
  --model_family unsigned_term_gene \
  --model_label canonical \
  --input_mode released_table \
  --signed_output false \
  --gene_set_pattern 'MyLibrary_<term>' \
  --distinct_algorithmic_feature 'unsigned conversion' \
  --description 'MyLibrary unsigned term-gene library using model U1.' \
  --options_json '{"term_column":"term","gene_id_column":"gene_id","gene_symbol_column":"gene_symbol","score_column":"score","term_prefix":"MyLibrary"}'

bash geneset-extractor-dev/run/library_onboard.sh validate \
  --bundle_dir ./MyLibrary_onboarding

bash geneset-extractor-dev/run/library_onboard.sh generate-package \
  --bundle_dir ./MyLibrary_onboarding \
  --out_dir ./MyLibrary_package
```

Then run the generated package:

```bash
cd MyLibrary_package
export APPTAINER_IMAGE=/path/to/geneset-extractor.sif
export DIG_DIR=/path/to/dig-gene-set-extractors
bash run/build_MyLibrary_genesets_apptainer.sh
bash run/validate_MyLibrary_outputs.sh
bash run/package_submission.sh
```

## Final Note

This workflow is designed to reduce back-and-forth and make your submission easier to review.

However, it only works cleanly for supported archetypes. If your library does not fit one of those patterns, the onboarding bundle is still useful, but the maintainer will need to implement the runnable package separately.
