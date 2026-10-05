#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/refresh_model_metadata_and_provenance_apptainer.sh [refresh args...]
  ./geneset-extractor-dev/run/refresh_model_metadata_and_provenance_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE

Optional environment variables:
  REPO_ROOT
  WORK_ROOT
  DIG_DIR
  APPTAINER_BIN
  APPTAINER_EXTRA_ARGS
  APPTAINER_PYTHON_BIN

Notes:
  - Arguments are forwarded to:
      geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh
  - Common path-bearing arguments like --model_dir, --description_template_tsv,
    --provenance_mirror_local_prefix, and --local_input_source_map_tsv are
    bind-mounted automatically.
EOF
}

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "Missing required file: ${path}" >&2
    exit 1
  fi
}

require_dir() {
  local path="$1"
  if [[ ! -d "${path}" ]]; then
    echo "Missing required directory: ${path}" >&2
    exit 1
  fi
}

append_bind_path() {
  local path="$1"
  if [[ -z "${path}" ]]; then
    return
  fi
  if [[ -d "${path}" ]]; then
    printf '%s\n' "${path}"
  elif [[ -e "${path}" ]]; then
    dirname "${path}"
  else
    dirname "${path}"
  fi
}

append_source_map_bind_paths() {
  local source_map_tsv="$1"
  local source_map_dir local_path
  [[ -n "${source_map_tsv}" && -f "${source_map_tsv}" ]] || return
  source_map_dir="$(cd -- "$(dirname -- "${source_map_tsv}")" && pwd -P)"
  while IFS= read -r local_path; do
    [[ -n "${local_path}" ]] || continue
    [[ "${local_path}" == /* ]] || local_path="${source_map_dir}/${local_path}"
    BIND_DIRS+=("$(append_bind_path "${local_path}")")
  done < <(
    awk -F $'\t' '
      NR == 1 {
        for (i = 1; i <= NF; i++) if ($i == "local_path") local_path_col = i
        next
      }
      local_path_col && $local_path_col != "" { print $local_path_col }
    ' "${source_map_tsv}"
  )
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "help" ]]; then
  usage
  exit 0
fi

require_dir "${DIG_DIR}"
if [[ -z "${APPTAINER_IMAGE}" ]]; then
  echo "Missing required environment variable: APPTAINER_IMAGE" >&2
  exit 1
fi
require_file "${APPTAINER_IMAGE}"

declare -a BIND_DIRS
BIND_DIRS+=("${REPO_ROOT}")
BIND_DIRS+=("${WORK_ROOT}")
BIND_DIRS+=("${DIG_DIR}")

FORWARDED_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model_dir|--description_template_tsv|--provenance_mirror_local_prefix|--local_input_source_map_tsv)
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

append_source_map_bind_paths "${LOCAL_INPUT_SOURCE_MAP_TSV:-}"

mapfile -t UNIQUE_BIND_DIRS < <(printf '%s\n' "${BIND_DIRS[@]}" | awk 'NF && !seen[$0]++')
BIND_ARG="$(IFS=,; printf '%s' "${UNIQUE_BIND_DIRS[*]}")"

REFRESH_PYTHON="${REPO_ROOT}/geneset-extractor-dev/src/refresh_model_metadata_and_provenance.py"
require_file "${REFRESH_PYTHON}"

declare -a EXEC_CMD
EXEC_CMD=(
  env "APPTAINERENV_DIG_DIR=${DIG_DIR}"
  "${APPTAINER_BIN}" exec
  --bind "${BIND_ARG}"
)
if [[ -n "${APPTAINER_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARGS=( ${APPTAINER_EXTRA_ARGS} )
  EXEC_CMD+=("${EXTRA_ARGS[@]}")
fi
EXEC_CMD+=(
  "${APPTAINER_IMAGE}"
  bash --noprofile --norc -c
  "exec $(printf '%q' "${APPTAINER_PYTHON_BIN}") $(printf '%q' "${REFRESH_PYTHON}") --dig_dir $(printf '%q' "${DIG_DIR}")$(printf ' %q' "${FORWARDED_ARGS[@]}")"
)

exec "${EXEC_CMD[@]}"
