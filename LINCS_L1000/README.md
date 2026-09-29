# LINCS L1000 submission modernization

This draft modernizes the existing LINCS L1000 HZ1 chemical-perturbation and
HZ2 CRISPR-knockout libraries. All matrix processing, ranking, mapping, and
GMT creation belong to `dig-gene-set-extractors`; this directory only supplies
declared inputs and dispatches DIG commands.

Run the committed HZ1 smoke fixture with:

```bash
SUBMISSION_WORK_DIR=/path/out DIG_REPO=../dig-gene-set-extractors \
  bash reproduction/reproduce.sh --smoke
```

For a full run set `LINCS_CHEMPERT_EXPRESSION_TSV`,
`LINCS_CRISPRKO_EXPRESSION_TSV`, and `LINCS_MAPPING_FILE`, then run
`bash reproduction/reproduce.sh full`.
