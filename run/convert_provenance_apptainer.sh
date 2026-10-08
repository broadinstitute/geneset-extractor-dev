#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_DIG_REPO="$(cd "${WRAPPER_DIR}/.." && pwd)/dig-gene-set-extractors"
# DIG_REPO is the established wrapper convention. DIG_DIR remains an explicit
# compatibility override for the cluster/refresh launchers.
DIG_DIR="${DIG_DIR:-${DIG_REPO:-${DEFAULT_DIG_REPO}}}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/convert_provenance_apptainer.sh <provenance.json-or-directory> [convert options]

Required environment variables:
  APPTAINER_IMAGE

Optional environment variables:
  DIG_REPO (or DIG_DIR), APPTAINER_BIN, APPTAINER_EXTRA_ARGS,
  APPTAINER_PYTHON_BIN

Supported convert options:
  --metadata PATH  --out PATH  --recursive  --overwrite

The command delegates to `python -m submission_tools provenance convert` in
the container. It converts persisted provenance only; it does not extract
gene sets or rewrite the legacy JSON, metadata, or source GMT.
EOF
}

append_bind_path() {
  local path="$1"
  if [[ -d "${path}" ]]; then printf '%s\n' "${path}"; else dirname "${path}"; fi
}

if [[ $# -lt 1 ]]; then usage >&2; exit 1; fi
case "$1" in -h|--help|help) usage; exit 0;; esac
INPUT_PATH="$1"
shift
if [[ ! -e "${INPUT_PATH}" ]]; then echo "Input does not exist: ${INPUT_PATH}" >&2; exit 1; fi
if [[ ! -d "${DIG_DIR}/src/geneset_extractors" ]]; then echo "DIG_DIR is not a DIG checkout: ${DIG_DIR}" >&2; exit 1; fi
if [[ -z "${APPTAINER_IMAGE}" || ! -f "${APPTAINER_IMAGE}" ]]; then echo "APPTAINER_IMAGE must name an existing image" >&2; exit 1; fi

declare -a BIND_DIRS FORWARDED_ARGS
BIND_DIRS=("${WRAPPER_DIR}" "${DIG_DIR}" "$(append_bind_path "${INPUT_PATH}")")
FORWARDED_ARGS=("${INPUT_PATH}")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --metadata|--out)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
      BIND_DIRS+=("$(append_bind_path "$2")")
      FORWARDED_ARGS+=("$1" "$2")
      shift 2
      ;;
    --recursive|--overwrite)
      FORWARDED_ARGS+=("$1")
      shift
      ;;
    *)
      echo "Unsupported option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mapfile -t UNIQUE_BIND_DIRS < <(printf '%s\n' "${BIND_DIRS[@]}" | awk 'NF && !seen[$0]++')
BIND_ARG="$(IFS=,; printf '%s' "${UNIQUE_BIND_DIRS[*]}")"
COMMAND="cd $(printf '%q' "${WRAPPER_DIR}") && exec $(printf '%q' "${APPTAINER_PYTHON_BIN}") -m submission_tools provenance convert$(printf ' %q' "${FORWARDED_ARGS[@]}") --dig-python $(printf '%q' "${APPTAINER_PYTHON_BIN}")"

EXEC_CMD=(env "APPTAINERENV_DIG_REPO=${DIG_DIR}" "${APPTAINER_BIN}" exec --bind "${BIND_ARG}")
if [[ -n "${APPTAINER_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARGS=( ${APPTAINER_EXTRA_ARGS} )
  EXEC_CMD+=("${EXTRA_ARGS[@]}")
fi
EXEC_CMD+=("${APPTAINER_IMAGE}" bash --noprofile --norc -c "${COMMAND}")
exec "${EXEC_CMD[@]}"
