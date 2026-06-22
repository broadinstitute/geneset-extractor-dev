#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

IMAGE_TAG="${IMAGE_TAG:-geneset-extractors-liger:md_liger}"
INPUT_ROOT="${INPUT_ROOT:-/Users/mduby/Data/Broad/GeneSetIncubator/Liger/H5adTestDataDocker}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/LIGER/outputs/docker_run}"
DATASET_COLUMN="${DATASET_COLUMN:-donor_id}"
CELL_TYPE_COLUMN="${CELL_TYPE_COLUMN:-cell_type__kp}"
ORGANISM="${ORGANISM:-human}"
GENOME_BUILD="${GENOME_BUILD:-hg38}"
MAX_CELLS_TOTAL="${MAX_CELLS_TOTAL:-50000}"
LIGER_TOP_N_GENES="${LIGER_TOP_N_GENES:-250}"
EXTRACTOR_TOP_K="${EXTRACTOR_TOP_K:-250}"
LIGER_K_GRID="${LIGER_K_GRID:-10,12,14,16,18,20,22,24}"
LIGER_N_REPS="${LIGER_N_REPS:-5}"
OVERWRITE="${OVERWRITE:-0}"

usage() {
  cat <<'EOF'
Usage:
  run/run_liger_docker.sh

Environment overrides:
  IMAGE_TAG
  INPUT_ROOT
  OUTPUT_ROOT
  DATASET_COLUMN
  CELL_TYPE_COLUMN
  ORGANISM
  GENOME_BUILD
  MAX_CELLS_TOTAL
  LIGER_TOP_N_GENES
  EXTRACTOR_TOP_K
  LIGER_K_GRID
  LIGER_N_REPS
  OVERWRITE=1

This script:
  1. builds the Docker image from geneset-extractor.Dockerfile
  2. mounts this repo at /work
  3. mounts INPUT_ROOT read-only at /inputs
  4. runs the LIGER h5ad batch workflow
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "${INPUT_ROOT}" ]]; then
  echo "Missing INPUT_ROOT directory: ${INPUT_ROOT}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

docker build \
  -f "${REPO_ROOT}/geneset-extractor.Dockerfile" \
  -t "${IMAGE_TAG}" \
  --build-arg DIG_BRANCH=md_liger \
  "${REPO_ROOT}"

docker run --rm \
  -v "${REPO_ROOT}:/work" \
  -v "${INPUT_ROOT}:/inputs:ro" \
  -v "${OUTPUT_ROOT}:/liger_outputs" \
  "${IMAGE_TAG}" \
  python LIGER/src/run_liger_h5ad_batch.py \
    --input_root /inputs \
    --out_root /liger_outputs \
    --dataset_column "${DATASET_COLUMN}" \
    --cell_type_column "${CELL_TYPE_COLUMN}" \
    --organism "${ORGANISM}" \
    --genome_build "${GENOME_BUILD}" \
    --max_cells_total "${MAX_CELLS_TOTAL}" \
    --liger_top_n_genes "${LIGER_TOP_N_GENES}" \
    --extractor_top_k "${EXTRACTOR_TOP_K}" \
    --liger_k_grid "${LIGER_K_GRID}" \
    --liger_n_reps "${LIGER_N_REPS}" \
    $([[ "${OVERWRITE}" == "1" ]] && printf '%s' "--overwrite")
