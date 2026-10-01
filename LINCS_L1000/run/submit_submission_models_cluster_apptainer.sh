#!/usr/bin/env bash
# Thin modern adapter for the established LINCS L1000 Apptainer array launcher.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
legacy_launcher="${root}/../run/submit_lincs_l1000_models_cluster_apptainer.sh"
submit=0
model_id=""
mode="--full"
array_memory="${SUBMISSION_ARRAY_MEMORY:-${LINCS_ARRAY_MEMORY:-16G}}"
array_walltime="${SUBMISSION_ARRAY_WALLTIME:-${LINCS_ARRAY_WALLTIME:-24:00:00}}"
smoke_memory="${SUBMISSION_SMOKE_MEMORY:-${LINCS_SUBMISSION_MEMORY:-4G}}"
smoke_walltime="${SUBMISSION_SMOKE_WALLTIME:-${LINCS_SUBMISSION_WALLTIME:-01:00:00}}"

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--model-id ID[,ID...]] [--submit]

--full writes the HZ1/HZ2 worklist unless --submit is supplied. --smoke runs
the committed HZ1 smoke fixture as one Apptainer job only with --submit. Set
SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout, APPTAINER_IMAGE,
DIG_REPO, LINCS_CHEMPERT_EXPRESSION_TSV, LINCS_CRISPRKO_EXPRESSION_TSV, and
LINCS_MAPPING_FILE. Resource settings are SUBMISSION_ARRAY_MEMORY and
SUBMISSION_ARRAY_WALLTIME for full arrays, and SUBMISSION_SMOKE_MEMORY and
SUBMISSION_SMOKE_WALLTIME for the smoke job. Legacy LINCS_* variables remain
fallbacks.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke) mode="--smoke" ;;
    --full) mode="--full" ;;
    --submit) submit=1 ;;
    --model-id) [[ $# -ge 2 ]] || { echo "Missing value for --model-id" >&2; exit 2; }; model_id="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
if [[ "${mode}" == "--smoke" ]]; then
  [[ -z "${model_id}" ]] || { echo "--model-id is supported only with --full" >&2; exit 2; }
  if [[ ${submit} -eq 0 ]]; then
    echo "Would run one smoke job through run_submission_models_apptainer.sh. Set --submit to call qsub."
    exit 0
  fi
  mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
  exec "${QSUB_BIN:-qsub}" -N "lincs_l1000_submission_smoke" \
    -o "${SUBMISSION_WORK_DIR}/qsub_logs/lincs_l1000_submission_smoke.out" \
    -e "${SUBMISSION_WORK_DIR}/qsub_logs/lincs_l1000_submission_smoke.err" \
    -l "h_vmem=${smoke_memory},h_rt=${smoke_walltime}" \
    bash "${root}/run/run_submission_models_apptainer.sh" --smoke
fi
command=(env "WORK_ROOT=${SUBMISSION_WORK_DIR}" "LINCS_OUT_ROOT=${SUBMISSION_WORK_DIR}" "DIG_DIR=${DIG_REPO:-}" \
  "LINCS_ARRAY_MEMORY=${array_memory}" "LINCS_ARRAY_WALLTIME=${array_walltime}" \
  "LINCS_CHEMPERT_EXPRESSION_TSV=${LINCS_CHEMPERT_EXPRESSION_TSV:-}" \
  "LINCS_CRISPRKO_EXPRESSION_TSV=${LINCS_CRISPRKO_EXPRESSION_TSV:-}" \
  "LINCS_CP_SIGNATURE_MANIFEST_TSV=${LINCS_CP_SIGNATURE_MANIFEST_TSV:-}" \
  "LINCS_CP_CACHE_DIR=${LINCS_CP_CACHE_DIR:-}" \
  "LINCS_MAPPING_FILE=${LINCS_MAPPING_FILE:-}" "${legacy_launcher}" --submit)
[[ -n "${model_id}" ]] && command+=(--model_id "${model_id}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit LINCS L1000 array: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
