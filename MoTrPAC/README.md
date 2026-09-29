# MoTrPAC submission modernization

This draft modernizes the existing MoTrPAC model matrix. Substantive
preprocessing, normalization, differential testing, mapping, ranking, and GMT
construction belong in `dig-gene-set-extractors`; this directory configures and
dispatches the existing DIG-backed MoTrPAC runners.

Run the committed HZ1 released-DEA smoke fixture with:

```bash
SUBMISSION_WORK_DIR=/path/to/motrpac_smoke DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

For a full run, set every `MOTRPAC_*` input variable listed in
`reproduction/input_manifest.tsv`, then run:

```bash
bash run/run_submission_models_apptainer.sh --full
```

The cluster adapter uses the common modern interface and delegates to the
existing MoTrPAC Apptainer array launcher:

```bash
export DIG_REPO=/path/to/dig-gene-set-extractors
export SUBMISSION_WORK_DIR=/scratch/motrpac_all_models
export APPTAINER_IMAGE=/path/to/geneset-extractor.sif
export MOTRPAC_RAW_COUNTS_DIR=/path/to/raw_counts
export MOTRPAC_TRANSCRIPT_METADATA_TSV=/path/to/transcript_metadata.tsv.gz
export MOTRPAC_PHENOTYPE_METADATA_TSV=/path/to/phenotype_metadata.tsv.gz
export MOTRPAC_FEATURE_TO_GENE_TSV=/path/to/feature_to_gene.tsv.gz
export MOTRPAC_RAT_TO_HUMAN_TSV=/path/to/rat_to_human.tsv.gz
export MOTRPAC_FEATURE_ANNOT=/path/to/TRNSCRPT_FEATURE_ANNOT.txt
export MOTRPAC_DEA_DIR=/path/to/dea
export MOTRPAC_MAPPING_FILE=/path/to/mappingFile_2017.txt
export SUBMISSION_ARRAY_MEMORY=24G
export SUBMISSION_ARRAY_WALLTIME=24:00:00
bash run/submit_submission_models_cluster_apptainer.sh --full --submit
```

Use `--model-id`, `--tissue-id`, or `--model-group` with `--full` to select a
declared subset. Outputs are written under `$SUBMISSION_WORK_DIR`.
