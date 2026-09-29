# HuBMAP submission modernization

This is a draft modernization of the existing HuBMAP HZ1 and HZ2 libraries.
All ASCT+B preprocessing, gene mapping, augmentation, and GMT generation are
implemented in `dig-gene-set-extractors`; this directory only selects models,
supplies declared inputs, and launches DIG.

Run the committed HZ1 smoke fixture with:

```bash
SUBMISSION_WORK_DIR=/path/out DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

For a full run, set `HUBMAP_RAW_ASCTB_DIR` and `HUBMAP_HUMAN_GENE_INFO` to the
declared inputs, then run `bash reproduction/reproduce.sh full`. HZ2 uses the
declared GeneShot service and is intentionally not part of the smoke run.
