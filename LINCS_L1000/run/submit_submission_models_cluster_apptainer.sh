#!/usr/bin/env bash
# Thin modern adapter for the established LINCS L1000 Apptainer array launcher.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
legacy_launcher="${root}/../run/submit_lincs_l1000_models_cluster_apptainer.sh"
submit=0
model_id=""

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--model-id ID[,ID...]] [--submit]

Writes the HZ1/HZ2 worklist unless --submit is supplied. Set
SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout, APPTAINER_IMAGE,
DIG_REPO, LINCS_CHEMPERT_EXPRESSION_TSV, LINCS_CRISPRKO_EXPRESSION_TSV, and
LINCS_MAPPING_FILE. Resource settings are SUBMISSION_ARRAY_MEMORY and
SUBMISSION_ARRAY_WALLTIME; legacy LINCS_ARRAY_* variables remain fallbacks.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --submit) submit=1 ;;
    --model-id) [[ $# -ge 2 ]] || { echo "Missing value for --model-id" >&2; exit 2; }; model_id="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
command=(env "WORK_ROOT=${SUBMISSION_WORK_DIR}" "LINCS_OUT_ROOT=${SUBMISSION_WORK_DIR}" "DIG_DIR=${DIG_REPO:-}" \
  "LINCS_ARRAY_MEMORY=${SUBMISSION_ARRAY_MEMORY:-${LINCS_ARRAY_MEMORY:-16G}}" \
  "LINCS_ARRAY_WALLTIME=${SUBMISSION_ARRAY_WALLTIME:-${LINCS_ARRAY_WALLTIME:-24:00:00}}" \
  "LINCS_CHEMPERT_EXPRESSION_TSV=${LINCS_CHEMPERT_EXPRESSION_TSV:-}" \
  "LINCS_CRISPRKO_EXPRESSION_TSV=${LINCS_CRISPRKO_EXPRESSION_TSV:-}" \
  "LINCS_MAPPING_FILE=${LINCS_MAPPING_FILE:-}" "${legacy_launcher}" --submit)
[[ -n "${model_id}" ]] && command+=(--model_id "${model_id}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit LINCS L1000 array: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
