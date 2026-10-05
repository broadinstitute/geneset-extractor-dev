#!/usr/bin/env bash
set -euo pipefail
mode="${1:---smoke}"; shift || true
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: run_submission_models_apptainer.sh [--smoke|--full] [--models HZ1[,HZ2]]" >&2; exit 2 ;; esac
[[ "${mode}" == "full" ]] && mode="--full"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  export PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
  export PYTHONPATH="${DIG_REPO}/src${PYTHONPATH:+:${PYTHONPATH}}"
  exec bash "${root}/reproduction/reproduce.sh" "${mode}" "$@"
fi
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}"
bind_csv="${root},${DIG_REPO},${SUBMISSION_WORK_DIR}"
for input_variable in IDG_DRUG_TARGETS_GMT IDG_ARCHS4_COEXP_GMT; do
  if [[ -n "${!input_variable:-}" ]]; then
    [[ -f "${!input_variable}" ]] || { echo "${input_variable} must identify an existing GMT file" >&2; exit 1; }
    bind_csv+="$(printf ',%s' "$(cd -- "$(dirname -- "${!input_variable}")" && pwd -P)")"
  fi
done
APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 APPTAINERENV_DIG_REPO="${DIG_REPO}" APPTAINERENV_SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" APPTAINERENV_IDG_DRUG_TARGETS_GMT="${IDG_DRUG_TARGETS_GMT:-}" APPTAINERENV_IDG_ARCHS4_COEXP_GMT="${IDG_ARCHS4_COEXP_GMT:-}" APPTAINERENV_IDG_DRUG_TARGETS_SOURCE_URL="${IDG_DRUG_TARGETS_SOURCE_URL:-}" APPTAINERENV_IDG_ARCHS4_COEXP_SOURCE_URL="${IDG_ARCHS4_COEXP_SOURCE_URL:-}" \
  "${APPTAINER_BIN:-apptainer}" exec --bind "${bind_csv}" "${APPTAINER_IMAGE}" bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" "$@"
