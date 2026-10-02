#!/usr/bin/env bash
# Run the declared RummaGEO submission contract inside Apptainer.
set -euo pipefail

mode="${1:---smoke}"
shift || true
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: run_submission_models_apptainer.sh [--smoke|--full] [--models ID[,ID...]]" >&2; exit 2 ;; esac
[[ "${mode}" == "full" ]] && mode="--full"

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  export PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
  exec bash "${root}/reproduction/reproduce.sh" "${mode}" "$@"
fi

[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a dig-gene-set-extractors checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the RummaGEO checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}"

if [[ "${mode}" == "--full" ]]; then
  for variable in RUMMAGEO_HUMAN_GMT RUMMAGEO_MOUSE_GMT RUMMAGEO_SELECTION_MANIFEST RUMMAGEO_SOURCE_MANIFEST RUMMAGEO_HUMAN_GENE_INFO RUMMAGEO_MOUSE_GENE_INFO RUMMAGEO_GENE_ORTHOLOGS; do
    [[ -n "${!variable:-}" && -f "${!variable}" ]] || { echo "Set ${variable} to an existing full-run input file" >&2; exit 1; }
  done
fi

declare -A bind_paths=()
add_bind_path() {
  local path="$1"
  [[ -n "${path}" ]] || return
  if [[ -f "${path}" ]]; then path="$(cd -- "$(dirname -- "${path}")" && pwd -P)"; else path="$(cd -- "${path}" && pwd -P)"; fi
  bind_paths["${path}"]=1
}
add_bind_path "${root}"
add_bind_path "${DIG_REPO}"
add_bind_path "${SUBMISSION_WORK_DIR}"
if [[ "${mode}" == "--full" ]]; then
  for variable in RUMMAGEO_HUMAN_GMT RUMMAGEO_MOUSE_GMT RUMMAGEO_SELECTION_MANIFEST RUMMAGEO_SOURCE_MANIFEST RUMMAGEO_HUMAN_GENE_INFO RUMMAGEO_MOUSE_GENE_INFO RUMMAGEO_GENE_ORTHOLOGS RUMMAGEO_GENE_LEGACY_GMT RUMMAGEO_DRUG_LEGACY_GMT; do
    [[ -n "${!variable:-}" ]] && add_bind_path "${!variable}"
  done
fi
bind_csv="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"
extra_args=()
if [[ -n "${APPTAINER_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=(${APPTAINER_EXTRA_ARGS})
fi

echo "+ ${APPTAINER_BIN:-apptainer} exec --bind ${bind_csv} ${APPTAINER_IMAGE} ..."
APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" \
APPTAINERENV_DIG_REPO="${DIG_REPO}" \
APPTAINERENV_SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
APPTAINERENV_RUMMAGEO_HUMAN_GMT="${RUMMAGEO_HUMAN_GMT:-}" \
APPTAINERENV_RUMMAGEO_MOUSE_GMT="${RUMMAGEO_MOUSE_GMT:-}" \
APPTAINERENV_RUMMAGEO_SELECTION_MANIFEST="${RUMMAGEO_SELECTION_MANIFEST:-}" \
APPTAINERENV_RUMMAGEO_SOURCE_MANIFEST="${RUMMAGEO_SOURCE_MANIFEST:-}" \
APPTAINERENV_RUMMAGEO_HUMAN_GENE_INFO="${RUMMAGEO_HUMAN_GENE_INFO:-}" \
APPTAINERENV_RUMMAGEO_MOUSE_GENE_INFO="${RUMMAGEO_MOUSE_GENE_INFO:-}" \
APPTAINERENV_RUMMAGEO_GENE_ORTHOLOGS="${RUMMAGEO_GENE_ORTHOLOGS:-}" \
APPTAINERENV_RUMMAGEO_GENE_LEGACY_GMT="${RUMMAGEO_GENE_LEGACY_GMT:-}" \
APPTAINERENV_RUMMAGEO_DRUG_LEGACY_GMT="${RUMMAGEO_DRUG_LEGACY_GMT:-}" \
"${APPTAINER_BIN:-apptainer}" exec --bind "${bind_csv}" "${extra_args[@]}" "${APPTAINER_IMAGE}" \
  bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" "$@"
