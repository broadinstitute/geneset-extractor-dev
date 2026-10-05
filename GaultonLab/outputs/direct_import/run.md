# GaultonLab direct import

The 12 supplied GMTs were verified against `config/task_manifest.tsv` and
imported byte-for-byte. Standard metadata, legacy provenance, Dapper
provenance, model-sidecar, and white-paper artifacts were then refreshed.

```bash
PYTHON_BIN=dig-gene-set-extractors/.venv/bin/python \
DIG_REPO=dig-gene-set-extractors \
bash geneset-extractor-dev/GaultonLab/reproduction/reproduce.sh --full

PYTHON_BIN=dig-gene-set-extractors/.venv/bin/python \
DIG_REPO=dig-gene-set-extractors \
bash geneset-extractor-dev/GaultonLab/run/refresh_submission_models.sh
```
