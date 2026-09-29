#!/usr/bin/env bash
set -euo pipefail
[[ $# -le 1 ]] || { echo "usage: run_submission_models_apptainer.sh [--smoke|--full]" >&2; exit 2; }
mode="${1:---smoke}"
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: run_submission_models_apptainer.sh [--smoke|--full]" >&2; exit 2 ;; esac
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the MoTrPAC checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}"
declare -A bind_paths=()
add_bind_path() { local path="$1"; [[ -n "${path}" ]] || return; [[ -e "${path}" ]] || { echo "Missing bind input: ${path}" >&2; exit 1; }; [[ -f "${path}" ]] && path="$(dirname -- "${path}")"; bind_paths["$(cd -- "${path}" && pwd -P)"]=1; }
add_bind_path "${root}"; add_bind_path "${DIG_REPO}"; add_bind_path "${SUBMISSION_WORK_DIR}"
if [[ "${mode}" != "--smoke" ]]; then
  for name in MOTRPAC_RAW_COUNTS_DIR MOTRPAC_TRANSCRIPT_METADATA_TSV MOTRPAC_PHENOTYPE_METADATA_TSV MOTRPAC_FEATURE_TO_GENE_TSV MOTRPAC_RAT_TO_HUMAN_TSV MOTRPAC_FEATURE_ANNOT MOTRPAC_DEA_DIR MOTRPAC_MAPPING_FILE; do add_bind_path "${!name:-}"; done
fi
binds="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"
exec "${APPTAINER_BIN:-apptainer}" exec --bind "${binds}" "${APPTAINER_IMAGE}" env DIG_REPO="${DIG_REPO}" SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" MOTRPAC_RAW_COUNTS_DIR="${MOTRPAC_RAW_COUNTS_DIR:-}" MOTRPAC_TRANSCRIPT_METADATA_TSV="${MOTRPAC_TRANSCRIPT_METADATA_TSV:-}" MOTRPAC_PHENOTYPE_METADATA_TSV="${MOTRPAC_PHENOTYPE_METADATA_TSV:-}" MOTRPAC_FEATURE_TO_GENE_TSV="${MOTRPAC_FEATURE_TO_GENE_TSV:-}" MOTRPAC_RAT_TO_HUMAN_TSV="${MOTRPAC_RAT_TO_HUMAN_TSV:-}" MOTRPAC_FEATURE_ANNOT="${MOTRPAC_FEATURE_ANNOT:-}" MOTRPAC_DEA_DIR="${MOTRPAC_DEA_DIR:-}" MOTRPAC_MAPPING_FILE="${MOTRPAC_MAPPING_FILE:-}" bash "${root}/reproduction/reproduce.sh" "${mode}"
