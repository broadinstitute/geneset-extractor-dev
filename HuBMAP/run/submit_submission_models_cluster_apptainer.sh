#!/usr/bin/env bash
# Thin modern adapter for the established HuBMAP Apptainer array launcher.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
legacy_launcher="${root}/../run/submit_hubmap_models_cluster_apptainer.sh"
submit=0
model_id=""

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--full] [--model-id ID[,ID...]] [--submit]

HuBMAP currently supports full execution only; --full is accepted explicitly
for consistency with the other library launchers. Writes the HZ1/HZ2 worklist
unless --submit is supplied. Set
SUBMISSION_WORK_DIR outside the HuBMAP checkout, APPTAINER_IMAGE, DIG_REPO,
HUBMAP_RAW_ASCTB_DIR, and HUBMAP_HUMAN_GENE_INFO. HZ2 retains its declared
GeneShot network dependency.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full) ;;
    --smoke) echo "HuBMAP has no cluster smoke mode; use reproduction/reproduce.sh --smoke" >&2; exit 2 ;;
    --submit) submit=1 ;;
    --model-id) [[ $# -ge 2 ]] || { echo "Missing value for --model-id" >&2; exit 2; }; model_id="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the HuBMAP checkout" >&2; exit 1; }
command=(env "WORK_ROOT=${SUBMISSION_WORK_DIR}" "HUBMAP_OUT_ROOT=${SUBMISSION_WORK_DIR}" "DIG_DIR=${DIG_REPO:-}" \
  "HUBMAP_ARRAY_MEMORY=${SUBMISSION_ARRAY_MEMORY:-${HUBMAP_ARRAY_MEMORY:-16G}}" \
  "HUBMAP_ARRAY_WALLTIME=${SUBMISSION_ARRAY_WALLTIME:-${HUBMAP_ARRAY_WALLTIME:-24:00:00}}" \
  "HUBMAP_HUMAN_GENE_INFO=${HUBMAP_HUMAN_GENE_INFO:-}" "HUBMAP_RAW_ASCTB_DIR=${HUBMAP_RAW_ASCTB_DIR:-}" \
  "${legacy_launcher}" --submit)
[[ -n "${model_id}" ]] && command+=(--model_id "${model_id}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit HuBMAP array: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
