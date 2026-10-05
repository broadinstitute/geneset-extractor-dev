#!/usr/bin/env bash
set -euo pipefail
mode="${1:---smoke}"; shift || true
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  export PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
  exec bash "${root}/run/run_submission_models.sh" "${mode}" --out-root "${SUBMISSION_WORK_DIR}" "$@"
fi
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" && -n "${DIG_REPO:-}" && -d "${DIG_REPO}" && -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set APPTAINER_IMAGE, DIG_REPO, and SUBMISSION_WORK_DIR" >&2; exit 1; }
binds="${root},${DIG_REPO},${SUBMISSION_WORK_DIR}"
[[ "${mode}" != "--full" ]] || { [[ -f "${IMPC_ASSERTIONS_CSV_GZ:-}" && -f "${IMPC_SYMBOL_MAPPING_FILE:-}" ]] || { echo "Set IMPC_ASSERTIONS_CSV_GZ and IMPC_SYMBOL_MAPPING_FILE" >&2; exit 1; }; binds+=",$(dirname "${IMPC_ASSERTIONS_CSV_GZ}"),$(dirname "${IMPC_SYMBOL_MAPPING_FILE}")"; }
exec "${APPTAINER_BIN:-apptainer}" exec --bind "${binds}" "${APPTAINER_IMAGE}" env GENESET_EXTRACTORS_IN_APPTAINER=1 APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" DIG_REPO="${DIG_REPO}" SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" IMPC_ASSERTIONS_CSV_GZ="${IMPC_ASSERTIONS_CSV_GZ:-}" IMPC_SYMBOL_MAPPING_FILE="${IMPC_SYMBOL_MAPPING_FILE:-}" bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" "$@"
