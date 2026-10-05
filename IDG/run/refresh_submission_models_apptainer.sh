#!/usr/bin/env bash
set -euo pipefail
models="${1:-all}"; [[ "${models}" == "--models" ]] && { models="$2"; }
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"; dev_root="$(cd -- "${root}/.." && pwd -P)"
[[ -n "${SUBMISSION_WORK_DIR:-}" && -n "${DIG_REPO:-}" ]] || { echo "Set SUBMISSION_WORK_DIR and DIG_REPO" >&2; exit 1; }
if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  [[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE" >&2; exit 1; }
  APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
  APPTAINERENV_DIG_REPO="${DIG_REPO}" \
  APPTAINERENV_SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
  APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" \
    exec "${APPTAINER_BIN:-apptainer}" exec --bind "${root},${dev_root},${DIG_REPO},${SUBMISSION_WORK_DIR}" "${APPTAINER_IMAGE}" bash "$0" --models "${models}"
fi
[[ "${models}" == "all" ]] && models="HZ1,HZ2"
IFS=',' read -r -a ids <<< "${models}"
for model_id in "${ids[@]}"; do
  model_dir="${SUBMISSION_WORK_DIR}/genesets/idg/models/${model_id}"
  [[ -d "${model_dir}" ]] || { echo "Missing output: ${model_dir}" >&2; exit 1; }
  DIG_DIR="${DIG_REPO}" PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" bash "${dev_root}/run/refresh_model_metadata_and_provenance.sh" --model_id "${model_id}" --model_dir "${model_dir}" --description_template_tsv "${root}/config/model_description_templates.tsv" --python_bin "${APPTAINER_PYTHON_BIN:-python}"
done
