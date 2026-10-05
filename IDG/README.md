# IDG submission wrapper

This wrapper declares two IDG models: `HZ1` (`IDG_Drug_Targets_2022`) and
`HZ2` (`ARCHS4_IDG_Coexp`). The wrapper is intentionally thin. Acquisition,
parsing, filtering, GMT generation, and output metadata are implemented in
`dig-gene-set-extractors`.

Run the local, network-free smoke workflow:

```bash
SUBMISSION_WORK_DIR=/path/to/output DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

A full run can use user-downloaded named Enrichr GMTs (preferred for cluster
runs without outbound network access):

```bash
IDG_DRUG_TARGETS_GMT=/path/to/IDG_Drug_Targets_2022.gmt \
IDG_ARCHS4_COEXP_GMT=/path/to/ARCHS4_IDG_Coexp.gmt \
SUBMISSION_WORK_DIR=/path/to/output DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --full
```

The canonical Enrichr URLs are recorded by default. To record a different
retrieval URL, set `IDG_DRUG_TARGETS_SOURCE_URL` and/or
`IDG_ARCHS4_COEXP_SOURCE_URL`. If the corresponding GMT variable is unset,
DIG instead acquires that named library from Enrichr at runtime.

For Apptainer and cluster execution, use `run/run_submission_models_apptainer.sh`
and `run/submit_submission_models_cluster_apptainer.sh`. Following a completed
full run, invoke `run/refresh_submission_models_apptainer.sh` to create the
standard model metadata and refreshed provenance artifacts.
