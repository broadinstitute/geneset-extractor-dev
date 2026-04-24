#!/usr/bin/env bash
set -euo pipefail

COUNTS_GCT=""
SAMPLE_METADATA_TSV=""
SUBJECT_METADATA_TSV=""
TISSUE_LABEL=""
PREPARED_DIR=""
RUN_ROOT=""
PYTHON_BIN="python3"
GTF_PATH=""
ORGANISM="human"
GENOME_BUILD="hg38"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT_DIR="${REPO_ROOT}/geneset-extractor-dev/GTEx/run"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --counts_gct) COUNTS_GCT="$2"; shift 2 ;;
    --sample_metadata_tsv) SAMPLE_METADATA_TSV="$2"; shift 2 ;;
    --subject_metadata_tsv) SUBJECT_METADATA_TSV="$2"; shift 2 ;;
    --tissue_label) TISSUE_LABEL="$2"; shift 2 ;;
    --prepared_dir) PREPARED_DIR="$2"; shift 2 ;;
    --run_root) RUN_ROOT="$2"; shift 2 ;;
    --python_bin) PYTHON_BIN="$2"; shift 2 ;;
    --gtf) GTF_PATH="$2"; shift 2 ;;
    --organism) ORGANISM="$2"; shift 2 ;;
    --genome_build) GENOME_BUILD="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${COUNTS_GCT}" || -z "${SAMPLE_METADATA_TSV}" || -z "${SUBJECT_METADATA_TSV}" || -z "${TISSUE_LABEL}" || -z "${PREPARED_DIR}" || -z "${RUN_ROOT}" ]]; then
  echo "Usage: $0 --counts_gct <path> --sample_metadata_tsv <path> --subject_metadata_tsv <path> --tissue_label <label> --prepared_dir <dir> --run_root <dir> [--gtf <path>]" >&2
  exit 1
fi

bash "${SCRIPT_DIR}/prepare_gtex_tissue_inputs.sh"   --python_bin "${PYTHON_BIN}"   --counts_gct "${COUNTS_GCT}"   --sample_metadata_tsv "${SAMPLE_METADATA_TSV}"   --subject_metadata_tsv "${SUBJECT_METADATA_TSV}"   --tissue_label "${TISSUE_LABEL}"   --out_dir "${PREPARED_DIR}"

mkdir -p "$(dirname "${RUN_ROOT}")"
OUTPUT_ROOT="$(cd "$(dirname "${RUN_ROOT}")" && pwd)"
if [[ -f "${PREPARED_DIR}/naming_reference.md" ]]; then
  cp "${PREPARED_DIR}/naming_reference.md" "${OUTPUT_ROOT}/naming_reference.md"
fi

cmd=(
  bash "${SCRIPT_DIR}/run_all_gtex_models.sh"
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
