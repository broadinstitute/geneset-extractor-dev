#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
binds="${root},${DIG_REPO},${SUBMISSION_WORK_DIR}"
for path in "${LINCS_CHEMPERT_EXPRESSION_TSV:-}" "${LINCS_CRISPRKO_EXPRESSION_TSV:-}" "${LINCS_MAPPING_FILE:-}"; do
  [[ -n "${path}" ]] && binds+=",$(dirname "${path}")"
done
exec "${APPTAINER_BIN:-apptainer}" exec --bind "${binds}" "${APPTAINER_IMAGE}" \
  env DIG_REPO="${DIG_REPO}" SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
  LINCS_CHEMPERT_EXPRESSION_TSV="${LINCS_CHEMPERT_EXPRESSION_TSV:-}" \
  LINCS_CRISPRKO_EXPRESSION_TSV="${LINCS_CRISPRKO_EXPRESSION_TSV:-}" \
  LINCS_MAPPING_FILE="${LINCS_MAPPING_FILE:-}" \
  bash "${root}/reproduction/reproduce.sh" "$@"
