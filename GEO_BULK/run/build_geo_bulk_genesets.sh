#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"
INPUT_ROOT="${GEO_BULK_INPUT_ROOT:-${REPO_ROOT}/inputs/GEO_BULK}"
OUT_ROOT="${GEO_BULK_OUT_ROOT:-${REPO_ROOT}/geo_bulk_all_models}"

exec "${PYTHON_BIN}" \
  "${REPO_ROOT}/geneset-extractor-dev/GEO_BULK/src/build_geo_bulk_genesets.py" \
  --dig_dir "${DIG_DIR}" \
  --input_root "${INPUT_ROOT}" \
  --out_root "${OUT_ROOT}" \
  "$@"
