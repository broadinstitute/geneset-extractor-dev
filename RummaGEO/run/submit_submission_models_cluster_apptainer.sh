#!/usr/bin/env bash
# Submit a single reproducible RummaGEO Apptainer job; dry-run by default.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
mode="--full"
submit=0
model_id=""
full_memory="${SUBMISSION_ARRAY_MEMORY:-16G}"
full_walltime="${SUBMISSION_ARRAY_WALLTIME:-24:00:00}"
smoke_memory="${SUBMISSION_SMOKE_MEMORY:-4G}"
smoke_walltime="${SUBMISSION_SMOKE_WALLTIME:-01:00:00}"

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--model-id ID[,ID...]] [--submit]

Dry-runs by default and prints the qsub command. Set SUBMISSION_WORK_DIR,
APPTAINER_IMAGE, and DIG_REPO. A full run also requires the declared
RUMMAGEO_* input variables in reproduction/input_manifest.tsv. --model-id is
optional; omit it to run both declared RummaGEO models in one job.
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
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the RummaGEO checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
if [[ "${mode}" == "--smoke" ]]; then memory="${smoke_memory}"; walltime="${smoke_walltime}"; else memory="${full_memory}"; walltime="${full_walltime}"; fi
job_name="rummageo_submission_${mode#--}"
command=("${QSUB_BIN:-qsub}" -N "${job_name}" -o "${SUBMISSION_WORK_DIR}/qsub_logs/${job_name}.out" -e "${SUBMISSION_WORK_DIR}/qsub_logs/${job_name}.err" -l "h_vmem=${memory},h_rt=${walltime}" bash "${root}/run/run_submission_models_apptainer.sh" "${mode}")
[[ -n "${model_id}" ]] && command+=(--models "${model_id}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit RummaGEO job: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
