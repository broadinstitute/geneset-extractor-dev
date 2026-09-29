#!/usr/bin/env bash
# Run the declared GTEx submission reproduction contract inside Apptainer.
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke|full) ;;
  *) echo "usage: run_submission_models_apptainer.sh [--smoke|full]" >&2; exit 2 ;;
esac

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
dig_repo="${DIG_REPO:-$(cd -- "${root}/../.." && pwd -P)/dig-gene-set-extractors}"
work_root="${SUBMISSION_WORK_DIR:-}"
apptainer_bin="${APPTAINER_BIN:-apptainer}"
apptainer_image="${APPTAINER_IMAGE:-}"
apptainer_python="${APPTAINER_PYTHON_BIN:-python}"

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  export PYTHON_BIN="${apptainer_python}"
  exec bash "${root}/reproduction/reproduce.sh" "${mode}"
fi

require_directory() {
  [[ -d "$1" ]] || { echo "Missing required directory: $1" >&2; exit 1; }
}

require_file() {
  [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }
}

require_directory "${dig_repo}"
[[ -n "${work_root}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GTEx checkout" >&2; exit 1; }
mkdir -p "${work_root}"
require_file "${apptainer_image}"

if [[ "${mode}" == "full" ]]; then
  for variable in GTEX_V10_COUNTS_GCT GTEX_V10_SAMPLE_ATTRIBUTES_TSV GTEX_V10_SUBJECT_PHENOTYPES_TSV GTEX_V8_COUNTS_GCT GTEX_V8_SAMPLE_ATTRIBUTES_TSV GTEX_V8_SUBJECT_PHENOTYPES_TSV GTEX_V8_HUMAN_GENE_INFO GTEX_GTF; do
    [[ -n "${!variable:-}" ]] || { echo "Set required full-input variable: ${variable}" >&2; exit 1; }
    require_file "${!variable}"
  done
fi

declare -A bind_paths=()
add_bind_path() {
  local path="$1"
  [[ -n "${path}" ]] || return
  if [[ -f "${path}" ]]; then
    path="$(cd -- "$(dirname -- "${path}")" && pwd -P)"
  else
    path="$(cd -- "${path}" && pwd -P)"
  fi
  bind_paths["${path}"]=1
}

add_bind_path "${root}/../.."
add_bind_path "${dig_repo}"
add_bind_path "${work_root}"
if [[ "${mode}" == "full" ]]; then
  add_bind_path "${GTEX_V10_COUNTS_GCT}"
  add_bind_path "${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}"
  add_bind_path "${GTEX_V10_SUBJECT_PHENOTYPES_TSV}"
  add_bind_path "${GTEX_V8_COUNTS_GCT}"
  add_bind_path "${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}"
  add_bind_path "${GTEX_V8_SUBJECT_PHENOTYPES_TSV}"
  add_bind_path "${GTEX_V8_HUMAN_GENE_INFO}"
  add_bind_path "${GTEX_GTF}"
fi
bind_csv="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"

extra_args=()
if [[ -n "${APPTAINER_EXTRA_ARGS:-}" ]]; then
  # Match existing repository launchers: this variable holds space-separated
  # Apptainer options supplied by the caller.
  # shellcheck disable=SC2206
  extra_args=(${APPTAINER_EXTRA_ARGS})
fi

echo "+ ${apptainer_bin} exec --bind ${bind_csv} ${apptainer_image} ..."
APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
APPTAINERENV_PYTHON_BIN="${apptainer_python}" \
APPTAINERENV_DIG_REPO="${dig_repo}" \
APPTAINERENV_SUBMISSION_WORK_DIR="${work_root}" \
APPTAINERENV_GTEX_V10_COUNTS_GCT="${GTEX_V10_COUNTS_GCT:-}" \
APPTAINERENV_GTEX_V10_SAMPLE_ATTRIBUTES_TSV="${GTEX_V10_SAMPLE_ATTRIBUTES_TSV:-}" \
APPTAINERENV_GTEX_V10_SUBJECT_PHENOTYPES_TSV="${GTEX_V10_SUBJECT_PHENOTYPES_TSV:-}" \
APPTAINERENV_GTEX_V8_COUNTS_GCT="${GTEX_V8_COUNTS_GCT:-}" \
APPTAINERENV_GTEX_V8_SAMPLE_ATTRIBUTES_TSV="${GTEX_V8_SAMPLE_ATTRIBUTES_TSV:-}" \
APPTAINERENV_GTEX_V8_SUBJECT_PHENOTYPES_TSV="${GTEX_V8_SUBJECT_PHENOTYPES_TSV:-}" \
APPTAINERENV_GTEX_V8_HUMAN_GENE_INFO="${GTEX_V8_HUMAN_GENE_INFO:-}" \
APPTAINERENV_GTEX_GTF="${GTEX_GTF:-}" \
  "${apptainer_bin}" exec --bind "${bind_csv}" "${extra_args[@]}" \
  "${apptainer_image}" bash "${root}/run/run_submission_models_apptainer.sh" "${mode}"
