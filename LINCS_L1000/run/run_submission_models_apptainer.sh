#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "usage: run_submission_models_apptainer.sh [--smoke|--full]" >&2
  echo "Use submit_submission_models_cluster_apptainer.sh --full --submit to submit a cluster job." >&2
  exit 2
fi
mode="${1:---smoke}"
case "${mode}" in
  --smoke) reproduce_mode="--smoke" ;;
  --full|full) reproduce_mode="full" ;;
  *) echo "usage: run_submission_models_apptainer.sh [--smoke|--full]" >&2; exit 2 ;;
esac

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}"

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

add_bind_path "${root}"
add_bind_path "${DIG_REPO}"
add_bind_path "${SUBMISSION_WORK_DIR}"
for path in "${LINCS_CHEMPERT_EXPRESSION_TSV:-}" "${LINCS_CRISPRKO_EXPRESSION_TSV:-}" "${LINCS_MAPPING_FILE:-}" "${LINCS_CP_SIGNATURE_MANIFEST_TSV:-}" "${LINCS_CP_CACHE_DIR:-}"; do
  [[ -n "${path}" ]] && add_bind_path "${path}"
done
binds="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"
exec "${APPTAINER_BIN:-apptainer}" exec --bind "${binds}" "${APPTAINER_IMAGE}" \
  env DIG_REPO="${DIG_REPO}" SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
  LINCS_CHEMPERT_EXPRESSION_TSV="${LINCS_CHEMPERT_EXPRESSION_TSV:-}" \
  LINCS_CRISPRKO_EXPRESSION_TSV="${LINCS_CRISPRKO_EXPRESSION_TSV:-}" \
  LINCS_CP_SIGNATURE_MANIFEST_TSV="${LINCS_CP_SIGNATURE_MANIFEST_TSV:-}" \
  LINCS_CP_CACHE_DIR="${LINCS_CP_CACHE_DIR:-}" \
  LINCS_MAPPING_FILE="${LINCS_MAPPING_FILE:-}" \
  bash "${root}/reproduction/reproduce.sh" "${reproduce_mode}"
