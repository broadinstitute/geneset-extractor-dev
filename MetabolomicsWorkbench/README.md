# MetabolomicsWorkbench

`HZ1` reconstructs the historical Ma'ayan Lab/Harmonizome Metabolomics Workbench metabolite library from the official processed Harmonizome edge list. It treats the edge list as already human-symbol harmonized, deduplicates Gene × Metabolite edges, groups by source metabolite name, retains sets with at least five unique genes, and writes deterministic output.

Run the offline fixture:

```bash
DIG_REPO="$PWD/dig-gene-set-extractors" SUBMISSION_WORK_DIR=/tmp/mw_smoke \
  bash geneset-extractor-dev/MetabolomicsWorkbench/reproduction/reproduce.sh --smoke
```

For a full run, pin the current downloaded Harmonizome edge list, set `MW_HARMONIZOME_EDGES_TSV_GZ`, and use `full`. The December 2022 CFDE GMT is validation-only; use `src/compare_metabolomics_workbench_gmt.py` to compare it with a generated GMT.
