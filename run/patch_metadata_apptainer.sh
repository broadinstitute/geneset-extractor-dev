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
  ./geneset-extractor-dev/run/patch_metadata_apptainer.sh <geneset.meta.json> [metadata patch args...]
  ./geneset-extractor-dev/run/patch_metadata_apptainer.sh --help

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
  - The first positional argument must be the metadata JSON path.
  - Remaining arguments are forwarded to:
      geneset-extractor-dev/run/patch_metadata.sh
  - Common path-bearing arguments like --meta_out, --provenance_out,
    --provenance_overlay_json, and --upstream_provenance_graph_json are
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

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

case "$1" in
  -h|--help|help)
    usage
    exit 0
    ;;
esac

require_dir "${DIG_DIR}"
if [[ -z "${APPTAINER_IMAGE}" ]]; then
  echo "Missing required environment variable: APPTAINER_IMAGE" >&2
  exit 1
fi
require_file "${APPTAINER_IMAGE}"

METADATA_JSON="$1"
shift
require_file "${METADATA_JSON}"

declare -a BIND_DIRS
BIND_DIRS+=("${REPO_ROOT}")
BIND_DIRS+=("${WORK_ROOT}")
BIND_DIRS+=("$(append_bind_path "${METADATA_JSON}")")

FORWARDED_ARGS=("${METADATA_JSON}")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --meta_out|--provenance_out|--provenance_overlay_json|--upstream_provenance_graph_json)
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

PATCH_WRAPPER="${REPO_ROOT}/geneset-extractor-dev/run/patch_metadata.sh"

declare -a EXEC_CMD
EXEC_CMD=(
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
  bash -lc
  "export PYTHON_BIN='${APPTAINER_PYTHON_BIN}'; bash '${PATCH_WRAPPER}'$(printf ' %q' "${FORWARDED_ARGS[@]}")"
)

exec "${EXEC_CMD[@]}"
