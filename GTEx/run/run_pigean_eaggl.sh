#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GTEX_ROOT="${REPO_ROOT}/geneset-extractor-dev/GTEx"
OUT_DIR="${SCREEN_OUT_DIR:-${GTEX_ROOT}/outputs/pigean_eaggl}"
LOG_DIR="${OUT_DIR}"
LOG_PATH="${LOG_DIR}/run.log"

mkdir -p "${LOG_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

{
  printf '[%s] starting\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  "${PYTHON_BIN}" "${GTEX_ROOT}/src/run_pigean_eaggl.py" \
  --out_dir "${OUT_DIR}" \
  "$@"
  rc=$?
  printf '[%s] finished exit_code=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}"
  exit "${rc}"
} >> "${LOG_PATH}" 2>&1
