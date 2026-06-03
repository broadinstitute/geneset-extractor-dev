# Proposal: MoTrPAC Gene-Set Pipeline

This note proposes a MoTrPAC pipeline parallel to the current GTEx pipeline, but adapted to the available MoTrPAC transcriptomics test data under `inputs/MoTrPAC/`.

The pipeline now supports three related model shapes:

- `TR1`
  - one model per tissue
  - sex-combined
  - design includes training condition
  - covariate includes sex
- `TW1`
  - one model family per tissue
  - one signature per `tissue × sex × timepoint`
  - training vs control within each stratum
  - notebook-style naming such as `t68-liver_male_8w`
- `HZ1`
  - one model run across all tissues
  - starts from released DEA tables rather than raw counts
  - wraps the notebook-replica Harmonizome-style GMT builder

Unlike GTEx, this proposal is for rat transcriptomics inputs. The proposed output policy is:

- produce human-mapped gene sets only

## Goal

Build a CLI-first pipeline that:

1. prepares one MoTrPAC tissue input bundle
2. performs either:
   - one training-vs-control differential expression model per tissue
   - or one timewise training-vs-control model per `tissue × sex × timepoint`
   - or one all-tissues released-DEA notebook-style library build
3. converts the resulting DE tables into compact GMT gene sets
4. emits human-mapped gene sets only

## Available Test Inputs

The current test inputs under `inputs/MoTrPAC/motrpac_test/` include:

- `raw_counts_by_tissue/TRNSCRPT_LIVER_RAW_COUNTS.tsv.gz`
- `TRNSCRPT_META_sample_metadata.tsv.gz`
- `PHENO_sample_metadata.tsv.gz`
- `FEATURE_TO_GENE_transcriptomics_subset.tsv.gz`
- `RAT_TO_HUMAN_GENE.tsv.gz`
- `raw_counts_manifest.tsv`

These appear sufficient for a first-pass liver pipeline.

## Proposed Repository Layout

Create a new extractor area:

- `geneset-extractor-dev/MoTrPAC/`

with:

- `src/`
- `run/`
- `planning/`
- `outputs/`

## Proposed Planning Files

Under `geneset-extractor-dev/MoTrPAC/planning/`:

- `tissue_list.tsv`
- `model_list.tsv`
- `model_manifest.tsv`
- `pipeline_inputs.md`
- `motrpac_training_pipeline_proposal.md`

### Proposed `tissue_list.tsv`

For the first pass, one row per available raw-count tissue file.

Example first row:

- `liver`
- `Liver`
- `inputs/MoTrPAC/motrpac_test/raw_counts_by_tissue/TRNSCRPT_LIVER_RAW_COUNTS.tsv.gz`
- `true`

### Proposed `model_list.tsv`

For the first pass, three models:

- `TR1`
- `TW1`
- `HZ1`

Suggested metadata:

- `model_id=TR1`
- `model_family=training`
- `description=training_vs_control_with_sex_covariate`
- `enabled=false`
- `model_id=TW1`
- `model_family=timewise`
- `description=timewise_training_vs_control_notebook_style`
- `enabled=true`
- `model_id=HZ1`
- `model_family=hz_released_dea`
- `description=harmonizome_notebook_style_released_dea_all_tissues`
- `enabled=false`

### Proposed `model_manifest.tsv`

For `TR1`, define:

- design formula: `~ intervention + sex`
- coefficient of interest: training vs control
- organism source: rat
- output symbol space: human ortholog
- annotation mode: feature map plus rat-to-human mapping

For `TW1`, define:

- one signature per `tissue × sex × timepoint`
- training vs control within each stratum
- notebook-style signature naming:
  - `<tissue_code>-<tissue_slug>_<sex>_<timepoint>`
- example:
  - `t68-liver_male_8w`

For `HZ1`, define:

- released-DEA all-tissues workflow
- notebook-replica GMT-building behavior
- default output mode:
  - `gmt`
- default GMT format:
  - `legacy`

## Proposed Pipeline Stages

### 1. Tissue prep

Add:

- `src/build_motrpac_tissue_inputs.py`

Inputs:

- `--counts_tsv`
- `--transcript_metadata_tsv`
- `--phenotype_metadata_tsv`
- `--feature_to_gene_tsv`
- `--rat_to_human_tsv`
- `--tissue_label`
- `--out_dir`

Responsibilities:

- load one tissue raw-count matrix
- map count-column sample IDs to transcript metadata using vial/sample identifiers
- join transcript metadata to phenotype metadata
- derive a clean sample metadata table with:
  - `sample_id`
  - `pid`
  - `bid`
  - `sex`
  - `intervention`
  - `tissue`
- map `feature_ID` to rat gene identifiers
- map rat genes to human ortholog symbols
- write a prepared bundle

### 2. Differential expression models

Add:

- `src/run_motrpac_training_model.py`
- `src/run_motrpac_timewise_model.py`
- `src/run_motrpac_hz_released_dea_model.py`

Responsibilities:

- read prepared counts and sample metadata
- fit limma/voom with:
  - `~ intervention + sex`
- extract the training-vs-control coefficient
- write one DEG table for the tissue
- pass that DEG table to `dig-gene-set-extractors` `convert rna_deg`

`TW1` responsibilities:

- read prepared counts and sample metadata
- stratify samples by:
  - `sex`
  - `timepoint`
- within each stratum, fit limma/voom with:
  - `~ intervention`
- write one DEG table per stratum
- emit signatures with notebook-style names such as:
  - `t68-liver_male_8w`

`HZ1` responsibilities:

- run once across all tissues
- call the notebook-replica released-DEA workflow
- preserve the standalone script as the authoritative biological logic
- package outputs into the same outer model layout used by the rest of the pipeline

### 3. Top-level orchestrator

Add:

- `src/build_motrpac_genesets.py`
- `run/build_motrpac_genesets.sh`

Inputs:

- `--tissues` or `--tissues_file`
- `--models` or `--models_file`
- `--tissue_list`
- `--model_list`
- `--model_manifest`
- explicit metadata/mapping file paths
- `--dig_dir`
- `--out_root`
- `--overwrite`

`HZ1` additionally needs:

- `--feature_annot`
- `--dea_dir`
- `--mapping_file`
- optional `--gene_info`
- optional `--gene_csv`

## Proposed Output Layout

Parallel to GTEx:

- `outputs/genesets/<tissue>/prepared/`
- `outputs/genesets/<tissue>/models/TR1/`
- `outputs/genesets/<tissue>/models/TW1/`
- `outputs/genesets/all_tissues/models/HZ1/`

Prepared outputs:

- `tissue_counts.tsv`
- `sample_metadata.tsv`
- `design_summary.json`
- `naming_reference.md`

Model outputs:

- `workflow/training_deg.tsv`
- `workflow/run_motrpac_training_limma_voom.R`
- `workflow/...logs...`
- `tissue_extractor/genesets.gmt`
- `tissue_extractor/geneset.tsv`
- `tissue_extractor/geneset.full.tsv`
- `tissue_extractor/geneset.meta.json`
- `tissue_extractor/geneset.provenance.json`

`HZ1` keeps the same outer model layout but different inner workflow contents:

- `workflow/motrpac_processed.tsv`
- `workflow/motrpac_processing_audit.tsv`
- `tissue_extractor/gene_set_library_crisp.gmt`
- `tissue_extractor/gene_set_library_up_crisp.gmt`
- `tissue_extractor/gene_set_library_dn_crisp.gmt`
- adapter `tissue_extractor/genesets.gmt`

## Human-Mapped Output Policy

This proposal assumes human-mapped output gene sets only.

That means:

- rat transcript features are the source measurement space
- rat genes are used during count processing and DE
- final gene-set labels and membership should be written in human symbol space

This is different from GTEx, which is already human-native and therefore does not need ortholog conversion.

## Recommended Human-Mapping Rules

To keep behavior explicit and reproducible, the prep script should define fixed rules for rat-to-human mapping.

Recommended rules:

1. Drop features without a rat gene symbol or rat gene identifier.
2. Join to `RAT_TO_HUMAN_GENE.tsv.gz`.
3. Require one non-empty human target symbol for output.
4. If multiple rat features map to the same human symbol, collapse them before DE or before GMT emission using one fixed rule.

Recommended collapse rule:

- keep the feature with highest variance across retained samples

Alternative acceptable rule:

- run DE at the rat-feature level, then collapse to one human symbol after DE using the smallest adjusted p-value within each human symbol

The simpler and more GTEx-like implementation is:

- collapse before DE

## Suggested Gene Filtering

To align with the more notebook-like approach discussed for GTEx, the MoTrPAC prep/model path should do:

1. Drop rows without usable mapped symbols.
2. Deduplicate symbols.
3. Run `filterByExpr` inside the limma/voom workflow.

This is preferable to leaving all filtering to downstream GMT generation.

## Suggested Contrast Naming

Use one compact contrast per tissue:

- `training_vs_control`

Suggested gene-set names:

- `TR1__training_vs_control__pos`
- `TR1__training_vs_control__neg`

For `TW1`, use notebook-style signature names:

- `t68-liver_male_8w`
- `t68-liver_female_8w`

with signed output gene sets emitted from those signatures.

## Join Strategy To Validate During Implementation

The main implementation risk is sample-ID reconciliation across:

- counts matrix columns
- transcript metadata
- phenotype metadata

Based on the current test files, likely join keys are:

- counts column sample IDs to transcript metadata via `viallabel` or `vial_label`
- transcript metadata to phenotype metadata via `PID` and `BID`, with sample/vial checks where available

This should be validated explicitly during implementation and logged clearly.

## Minimal First Version

Scope the first implementation to:

- tissue: `liver`
- models:
  - `TR1`
  - `TW1`
- designs:
  - `TR1`: `~ intervention + sex`
  - `TW1`: `~ intervention` within each `sex × timepoint` stratum
- output symbol space: human ortholog only

No multi-tissue orchestration beyond what is needed for the single available tissue.

## Recommended Validation

At minimum:

- confirm retained sample counts by intervention and sex
- confirm expected factor levels in the final design matrix
- confirm number of features before and after:
  - symbol mapping
  - human ortholog mapping
  - deduplication
  - `filterByExpr`
- confirm final GMT set names and gene counts

## Summary

The MoTrPAC analogue of the GTEx pipeline should:

- prepare one tissue at a time
- fit either one sex-adjusted training-vs-control model per tissue or one notebook-style timewise family per tissue
- generate compact gene sets from the resulting training coefficients
- emit human-mapped gene sets only

The main MoTrPAC-specific complexity is not the DE model. It is the mapping path from rat transcript features to stable human output symbols.
