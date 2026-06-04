# Pipeline Inputs

This document lists the current inputs and environment requirements needed to run the GTEx pipeline end to end.

## Scope

The current top-level flow is:

1. `build_genesets.sh`
2. `run_pigean.sh`
3. `run_eaggl.sh`
4. `summarize_model_enrichment.sh`
5. `summarize_top_models.sh`

This file covers:

- biological data inputs
- planning/config inputs
- external repository inputs
- Python requirements
- R requirements

## Biological Data Inputs

These are the scientific input files needed to build GTEx gene sets.

### 1. GTEx counts GCT

Required by `build_genesets.sh` as an explicit CLI input:

- `--counts_gct`

This is now the runtime mechanism used to switch between versions such as GTEx v8 and v10.

Example for adipose subcutaneous:

- `inputs/GTEx/v10/gene_reads_v10_adipose_subcutaneous.gct.gz`

### 2. Sample metadata TSV

Required by `build_genesets.sh`.

Example:

- `inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt`

### 3. Subject metadata TSV

Required by `build_genesets.sh`.

Example:

- `inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt`

### 4. GTF annotation file

Required only when the selected models use `gtf_annotated` mode.

Example:

- `inputs/GTEx/v10/gencode.v39.annotation.gtf.gz`

### 5. `human_gene_info`

Required when the selected models include notebook-style `HZ*` aging-signature models.

This file is used for notebook-style Ensembl-to-symbol mapping inside the `dig` workflow:

- `geneset_extractors.cli workflows gtex_aging_signatures`

Example:

- `inputs/GTEx/v8/human_gene_info`

## Planning And Config Inputs

These files are part of the runtime configuration surface.

### 1. Model list

Used to define valid selectable model IDs and their enabled/default state.

- `geneset-extractor-dev/GTEx/planning/model_list.tsv`

### 2. Tissue list

Used to define valid selectable tissue IDs and map them to stable labels and metadata grouping values.

- `geneset-extractor-dev/GTEx/planning/tissue_list.tsv`

This now defaults from the repo-relative planning path in the active Python entrypoints unless overridden explicitly.

The tissue lists are no longer the authoritative source of the counts GCT path for runtime execution.

### 3. Continuous-age model manifest

Used by the continuous-age model runner.

- `geneset-extractor-dev/GTEx/planning/geneset_build/continuous_age_models/model_manifest.tsv`

### 4. Age-binned model manifest

Used by the age-binned model runner.

- `geneset-extractor-dev/GTEx/planning/geneset_build/age_binned_models/model_manifest.tsv`

## External Repository Inputs

These are required directories supplied explicitly at runtime.

### 1. `dig-gene-set-extractors`

Required by `build_genesets.sh`, which passes the path through to:

- `run_age_binned_model.py`
- `run_continuous_age_model.py`
- `run_hz_notebook_model.py`

Required CLI argument:

- `--dig_dir /path/to/dig-gene-set-extractors`

### 2. `pigean/src`

Required by:

- `run_pigean.sh`
- `run_eaggl.sh`

Required CLI argument:

- `--pigean_src /path/to/pigean/src`

### 3. PIGEAN bundle data directory

Required by:

- `run_pigean.sh`
- `run_eaggl.sh`

Required CLI argument:

- `--bundle_data_dir /path/to/pigean/bundles/model_small-2026.02.22/data`

## Python Requirements

### GTEx-local Python scripts

The active Python scripts under `geneset-extractor-dev/GTEx/src/` currently use only the Python standard library.

The main modules used are:

- `argparse`
- `csv`
- `gzip`
- `json`
- `math`
- `os`
- `re`
- `shlex`
- `shutil`
- `subprocess`
- `sys`
- `pathlib`
- `dataclasses`
- `datetime`
- `collections`
- `typing`

So there is no separate third-party Python package requirement for the GTEx-local wrappers themselves.

### Upstream Python dependencies

The pipeline also invokes external Python code from other repositories:

- `dig-gene-set-extractors`
- `pigean`

Those repositories may have their own Python package requirements. This planning document does not duplicate them; it assumes their environments are already installed and runnable.

## R Requirements

Continuous-age model generation requires:

- an explicit `Rscript` path supplied via `--rscript_bin`
- an R environment with these packages installed:
  - `edgeR`
  - `limma`

## Non-Input Runtime Defaults

These are not external scientific inputs, but they still affect execution:

- `--python_bin`
- `--rscript_bin`
- `--out_root`

If `--out_root` is omitted on the active top-level scripts, outputs default to:

- `./gtex_outputs/genesets`
- `./gtex_outputs/pigean_eaggl`

relative to the current working directory.

## Canonical Checklist

To run the full current pipeline, make sure you have:

- a model list TSV
- a tissue list TSV
- a counts GCT file supplied explicitly via `--counts_gct`
- a GTEx sample metadata TSV
- a GTEx subject metadata TSV
- a `human_gene_info` file when running `HZ*` notebook-style models
- a GTF file if the selected models require it
- a `dig-gene-set-extractors` checkout
- a `pigean/src` checkout
- a PIGEAN bundle data directory
- a Python interpreter that can run the GTEx and external Python code
- an `Rscript` binary with `edgeR` and `limma` installed

## Runtime Note

For the current `AB*` and `AC*` implementations, the authoritative runtime path now starts from raw GTEx inputs inside `dig` workflows:

- `geneset_extractors.cli workflows gtex_age_binned`
- `geneset_extractors.cli workflows gtex_continuous_age`

The top-level GTEx wrapper still selects tissues and models, but it no longer depends on a persistent `prepared/` bundle as the execution contract for those model families.

## Default Planning Paths

Unless overridden on the CLI, the active Python entrypoints currently default these planning/config files from the checked-out `geneset-extractor-dev/GTEx/planning/` tree:

- `--model_list`
- `--tissue_list`
- `--age_binned_model_manifest`
- `--continuous_age_model_manifest`

## `HZ1` Notes

`HZ1` now uses the `dig-gene-set-extractors` workflow:

- `geneset_extractors.cli workflows gtex_aging_signatures`

through the GTEx wrapper:

- `geneset-extractor-dev/GTEx/src/run_hz_notebook_model.py`

Important constraints:

- `HZ1` requires `--tissue_granularity broad`
- `HZ1` requires `--human_gene_info`
- `HZ1` uses the `counts_gct` path from the active broad tissue list as the raw expression GCT input

To match the original GTEx aging-signature notebook as closely as possible, the broad tissue list used for `HZ1` should point at the GTEx V8 raw reads GCT rather than a V10 counts matrix.
