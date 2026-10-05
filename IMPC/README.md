# IMPC

`IMPC` contains one model, `HZ1`: a reproducible reconstruction of the historical Harmonizome/Enrichr KOMP2 mouse-phenotype library from pinned IMPC Data Release 18 direct assertions.

Run the offline deterministic smoke package:

```bash
DIG_REPO="$PWD/dig-gene-set-extractors" SUBMISSION_WORK_DIR=/tmp/impc_smoke \
  bash geneset-extractor-dev/IMPC/reproduction/reproduce.sh --smoke
```

For a full run, set `IMPC_ASSERTIONS_CSV_GZ` and `IMPC_SYMBOL_MAPPING_FILE` as documented in `reproduction/input_manifest.tsv`, then replace `--smoke` with `full`. The legacy KOMP2 GMT is validation-only; compare a generated GMT using `src/compare_impc_legacy_gmt.py`.

The model groups direct `(MP term, marker)` assertions, normalizes case-insensitive symbols through `mappingFile_2017.txt`, deduplicates memberships, and retains sets with at least five genes. No ontology propagation, significance filtering, sex/zygosity filtering, or legacy-specific exceptions are used.
