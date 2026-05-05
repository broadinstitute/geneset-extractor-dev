#!/usr/bin/env bash
set -euo pipefail

PREPARED_DIR=""
RUN_ROOT=""
PYTHON_BIN="python3"
ORGANISM="human"
GENOME_BUILD="hg38"
GTF_PATH=""
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT_DIR="${REPO_ROOT}/geneset-extractor-dev/GTEx/run"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepared_dir) PREPARED_DIR="$2"; shift 2 ;;
    --run_root) RUN_ROOT="$2"; shift 2 ;;
    --python_bin) PYTHON_BIN="$2"; shift 2 ;;
    --organism) ORGANISM="$2"; shift 2 ;;
    --genome_build) GENOME_BUILD="$2"; shift 2 ;;
    --gtf) GTF_PATH="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${PREPARED_DIR}" || -z "${RUN_ROOT}" ]]; then
  echo "Usage: $0 --prepared_dir <dir> --run_root <dir> [--gtf <path>]" >&2
  exit 1
fi

for model_id in AB1 AB2 AB3 AB4 AB5 AB6 AB7 AB8 AB9 AB10 AB11 AB12 AB13 AB14 AB15 AB16 AB17 AB18 AB19 AB20 AB21 AB22; do
  cmd=(
    bash "${SCRIPT_DIR}/run_gtex_model.sh"
    --model_id "${model_id}"
    --prepared_dir "${PREPARED_DIR}"
    --run_root "${RUN_ROOT}"
    --python_bin "${PYTHON_BIN}"
    --organism "${ORGANISM}"
    --genome_build "${GENOME_BUILD}"
  )
  if [[ -n "${GTF_PATH}" ]]; then
    cmd+=(--gtf "${GTF_PATH}")
  fi
  "${cmd[@]}"
done
