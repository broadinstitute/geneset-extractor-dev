#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -d "${DIG_DIR}" ]]; then
  echo "Missing dig-gene-set-extractors directory: ${DIG_DIR}" >&2
  exit 1
fi

exec "${PYTHON_BIN}" \
  "${REPO_ROOT}/geneset-extractor-dev/src/refresh_model_metadata_and_provenance.py" \
  --dig_dir "${DIG_DIR}" \
  "$@"
