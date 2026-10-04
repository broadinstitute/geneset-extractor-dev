#!/usr/bin/env bash
# Run the declared GlyGen submission contract inside Apptainer.
set -euo pipefail

mode="${1:---smoke}"
shift || true
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: run_submission_models_apptainer.sh [--smoke|--full] [--models HZ1,HZ2]" >&2; exit 2;; esac
[[ "${mode}" == "full" ]] && mode="--full"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  export PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
  export PYTHONPATH="${DIG_REPO}/src${PYTHONPATH:+:${PYTHONPATH}}"
  exec bash "${root}/run/run_submission_models.sh" "${mode}" --out-root "${SUBMISSION_WORK_DIR}" "$@"
fi

[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GlyGen checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}"
full_variables=(GLYGEN_UNICARBKB_CSV GLYGEN_HARVARD_CSV GLYGEN_GLYCONNECT_CSV GLYGEN_PROTEIN_MASTERLIST_CSV GLYGEN_API_CACHE_MANIFEST_TSV)
if [[ "${mode}" == "--full" ]]; then
  for variable in "${full_variables[@]}"; do
    [[ -n "${!variable:-}" && -f "${!variable}" ]] || { echo "Set ${variable} to an existing full-run input file" >&2; exit 1; }
  done
fi
declare -A bind_paths=()
add_bind_path() { local path="$1"; [[ -n "${path}" ]] || return; [[ -e "${path}" ]] || { echo "Missing bind input: ${path}" >&2; exit 1; }; [[ -f "${path}" ]] && path="$(dirname -- "${path}")"; bind_paths["$(cd -- "${path}" && pwd -P)"]=1; }
add_bind_path "${root}"; add_bind_path "${DIG_REPO}"; add_bind_path "${SUBMISSION_WORK_DIR}"
if [[ "${mode}" == "--full" ]]; then for variable in "${full_variables[@]}"; do add_bind_path "${!variable}"; done; fi
binds="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"
exec "${APPTAINER_BIN:-apptainer}" exec --bind "${binds}" "${APPTAINER_IMAGE}" env \
  GENESET_EXTRACTORS_IN_APPTAINER=1 APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" \
  DIG_REPO="${DIG_REPO}" SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
  GLYGEN_UNICARBKB_CSV="${GLYGEN_UNICARBKB_CSV:-}" GLYGEN_HARVARD_CSV="${GLYGEN_HARVARD_CSV:-}" \
  GLYGEN_GLYCONNECT_CSV="${GLYGEN_GLYCONNECT_CSV:-}" GLYGEN_PROTEIN_MASTERLIST_CSV="${GLYGEN_PROTEIN_MASTERLIST_CSV:-}" \
  GLYGEN_API_CACHE_MANIFEST_TSV="${GLYGEN_API_CACHE_MANIFEST_TSV:-}" \
  bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" "$@"
