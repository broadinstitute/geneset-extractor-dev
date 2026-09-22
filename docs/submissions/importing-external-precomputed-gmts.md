# Importing externally generated GMTs

Use this path when a documented external release provides one or more GMTs but
complete regeneration code is unavailable. It validates and imports supplied
GMTs unchanged; it does not claim to reproduce the external scientific method.

Prepare one source manifest and one row per GMT/model:

```bash
python3 -m submission_tools import-external-library \
  --library-id EXTERNAL_LIBRARY \
  --display-name "External library" \
  --source-manifest source.yaml \
  --gmt-manifest external_gmts.tsv \
  --gmt-root /read-only/external-gmts \
  --output EXTERNAL_LIBRARY
```

`source.yaml` must record source identity, release, license, access terms,
organism, genome build, assay, data type, and documentation. The tab-delimited
GMT manifest requires `model_id`, `display_name`, `source_gmt_path`, `sha256`,
`description`, and `partition_id`. Paths must be beneath `--gmt-root`; an empty
checksum is calculated, while a wrong supplied checksum is rejected.
The recorded checksum is checked again at materialization time, so a source
GMT changed after scaffolding is rejected rather than silently republished.

For materialization, point the generated thin wrapper at the read-only source
root and a separate runtime-output directory:

```bash
cd EXTERNAL_LIBRARY
EXTERNAL_GMT_INPUT_ROOT=/read-only/external-gmts \
SUBMISSION_WORK_DIR=/work/external-library \
PYTHONPATH=/path/to/dig-gene-set-extractors/src \
bash reproduction/reproduce.sh full
```

Each model receives unchanged `genesets.gmt`, metadata, and paired
`geneset.provenance.legacy.json` / `geneset.provenance.dapper.yaml` sidecars.
The provenance records the externally documented generation and the local
checksum-verified import. It does not assert that DIG or the wrapper performed
the unavailable scientific processing.
