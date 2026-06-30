#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/write_igvf_model_json_apptainer.sh [run_igvf_perturbseq_model.py args...]
  ./geneset-extractor-dev/run/write_igvf_model_json_apptainer.sh --help
EOF
}

require_dir() { [[ -d "$1" ]] || { echo "Missing required directory: $1" >&2; exit 1; }; }
require_file() { [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }; }
append_bind_path() { [[ -d "$1" ]] && printf '%s\n' "$1" || dirname "$1"; }

[[ $# -ge 1 ]] || { usage >&2; exit 1; }
case "${1:-}" in
  -h|--help|help) usage; exit 0 ;;
esac

require_dir "${DIG_DIR}"
[[ -n "${APPTAINER_IMAGE}" ]] || { echo "Missing required environment variable: APPTAINER_IMAGE" >&2; exit 1; }
require_file "${APPTAINER_IMAGE}"

declare -a BIND_DIRS
BIND_DIRS+=("${REPO_ROOT}" "${DIG_DIR}")
FORWARDED_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run_root|--expression_tsv|--mapping_file|--model_manifest|--provenance_mirror_local_prefix)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      BIND_DIRS+=("$(append_bind_path "$2")")
      FORWARDED_ARGS+=("$1" "$2")
      shift 2
      ;;
    *)
      FORWARDED_ARGS+=("$1")
      shift
      ;;
  esac
done

mapfile -t UNIQUE_BIND_DIRS < <(printf '%s\n' "${BIND_DIRS[@]}" | awk 'NF && !seen[$0]++')
BIND_ARG="$(IFS=,; printf '%s' "${UNIQUE_BIND_DIRS[*]}")"
RUNNER="${REPO_ROOT}/geneset-extractor-dev/IGVF/src/run_igvf_perturbseq_model.py"

declare -a EXEC_CMD
EXEC_CMD=("${APPTAINER_BIN}" exec --bind "${BIND_ARG}")
if [[ -n "${APPTAINER_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARGS=( ${APPTAINER_EXTRA_ARGS} )
  EXEC_CMD+=("${EXTRA_ARGS[@]}")
fi
EXEC_CMD+=(
  "${APPTAINER_IMAGE}"
  bash --noprofile --norc -c
  "export PYTHONPATH='${DIG_DIR}/src'; '${APPTAINER_PYTHON_BIN}' '${RUNNER}'$(printf ' %q' "${FORWARDED_ARGS[@]}") --write_model_only"
)

exec "${EXEC_CMD[@]}"
