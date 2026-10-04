# GlyGen

Library ID: `GlyGen`. `HZ1` is the `glycosylated_proteins` model and `HZ2` is the `glycan_synthesizing_enzymes` model.

The wrapper is intentionally thin; all transformation logic and output metadata are in DIG. Run the deterministic smoke package with:

```bash
DIG_REPO="$PWD/dig-gene-set-extractors" bash geneset-extractor-dev/GlyGen/reproduction/reproduce.sh --smoke
```

For the full v1.12.1 model, set the four `GLYGEN_*_CSV` variables in `reproduction/input_manifest.tsv` and run the same command with `full`.

For the enzyme model, first obtain an independent GlyTouCan accession snapshot (never the historical validation GMT) and acquire responses:

```bash
PYTHONPATH="$PWD/dig-gene-set-extractors/src" python3 -m geneset_extractors.cli convert glygen_glycan_synthesizing_enzymes_acquire --accessions_tsv "$GLYGEN_GLYCAN_ACCESSIONS_TSV" --cache_dir inputs/GlyGen/api_cache --manifest inputs/GlyGen/glygen_api_manifest.tsv
```

Set `GLYGEN_API_CACHE_MANIFEST_TSV=inputs/GlyGen/glygen_api_manifest.tsv` for the full wrapper run. The cache manifest records requests, timestamps, paths, checksums, and failures. Retain failed rows and retry explicitly; the transformation only consumes successful cached responses.

`glycosylated_proteins` is a scientific reimplementation of the legacy 2022 library. It deliberately keeps candidate-only glycans and does not use `mappingFile_2017.txt`. `glycan_synthesizing_enzymes` filters `enzyme[]` to `tax_id == 9606`; its API data are labeled GlyGen Sandbox (`xref_key=glycan_xref_sandbox`) and may differ from the September 2026 validation snapshot.
