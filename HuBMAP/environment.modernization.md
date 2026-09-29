# HuBMAP modernization environment

The wrapper requires Python with the DIG package's HuBMAP workflow dependencies
(`pandas`, `numpy`, and `tqdm`). Full HZ2 reproduction additionally requires
network access to the declared GeneShot endpoint. Production cluster jobs use
the existing Apptainer image and `APPTAINER_IMAGE`.

Set `DIG_REPO` to the checked-out `dig-gene-set-extractors` repository and set
`SUBMISSION_WORK_DIR` to an untracked directory outside this checkout.
