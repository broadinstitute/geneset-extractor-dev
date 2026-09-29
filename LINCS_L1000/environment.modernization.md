# LINCS L1000 modernization environment

The wrapper requires Python with DIG's LINCS workflow dependencies (`pandas` and
`numpy`). Set `DIG_REPO` to the checked-out `dig-gene-set-extractors` repository
and set `SUBMISSION_WORK_DIR` to an untracked directory outside this checkout.
Production cluster jobs use the existing Apptainer image and `APPTAINER_IMAGE`.
