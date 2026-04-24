#!/usr/bin/env bash
set -euo pipefail

MODELS_ROOT=""
OUT_DIR=""
PYTHON_BIN="python3"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MODEL_MANIFEST="${REPO_ROOT}/geneset-extractor-dev/GTEx/planning/gtex_model_step1/model_manifest.tsv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --models_root) MODELS_ROOT="$2"; shift 2 ;;
    --out_dir) OUT_DIR="$2"; shift 2 ;;
    --python_bin) PYTHON_BIN="$2"; shift 2 ;;
    --model_manifest) MODEL_MANIFEST="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${MODELS_ROOT}" || -z "${OUT_DIR}" ]]; then
  echo "Usage: $0 --models_root <dir> --out_dir <dir> [--python_bin python3]" >&2
  exit 1
fi

"${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/GTEx/src/check_identical_gtex_models.py" \
  --models_root "${MODELS_ROOT}" \
  --out_dir "${OUT_DIR}" \
  --model_manifest "${MODEL_MANIFEST}"
