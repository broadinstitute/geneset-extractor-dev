#!/usr/bin/env bash
# Submit independently merge-free HZ4 cell-line × perturbation-time tasks as an SGE array.
set -euo pipefail

submit=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --submit) submit=1 ;;
    -h|--help)
      echo "Usage: submit_hz4_cell_line_time_cluster_apptainer.sh [--submit]"
      echo "Run plan_hz4_cell_line_time_apptainer.sh first; then this submits one task per manifest row."
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
plan_dir="${HZ4_PARTITION_PLAN_DIR:-${SUBMISSION_WORK_DIR}/genesets/hz4_cell_line_time_plan}"
manifest="${plan_dir}/task_manifest.tsv"
[[ -f "${manifest}" ]] || { echo "Missing HZ4 task manifest: ${manifest}. Run plan_hz4_cell_line_time_apptainer.sh first." >&2; exit 1; }
task_count="$(awk 'NR > 1 { count += 1 } END { print count + 0 }' "${manifest}")"
[[ "${task_count}" -gt 0 ]] || { echo "HZ4 task manifest has no tasks: ${manifest}" >&2; exit 1; }
max_concurrent="${HZ4_MAX_CONCURRENT_TASKS:-10}"
memory="${HZ4_TASK_MEMORY:-${SUBMISSION_ARRAY_MEMORY:-${LINCS_ARRAY_MEMORY:-3G}}}"
walltime="${HZ4_TASK_WALLTIME:-${SUBMISSION_ARRAY_WALLTIME:-${LINCS_ARRAY_WALLTIME:-24:00:00}}}"
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
task_command="exec $(printf '%q' "${root}/run/run_hz4_cell_line_time_task_apptainer.sh") --task-id \"\${SGE_TASK_ID}\""
command=("${QSUB_BIN:-qsub}" -N lincs_hz4_cell_time -t "1-${task_count}" -tc "${max_concurrent}" \
  -o "${SUBMISSION_WORK_DIR}/qsub_logs/lincs_hz4_cell_time.out" \
  -e "${SUBMISSION_WORK_DIR}/qsub_logs/lincs_hz4_cell_time.err" \
  -l "h_vmem=${memory},h_rt=${walltime}" \
  bash -c "${task_command}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit %s HZ4 tasks (at most %s concurrently): ' "${task_count}" "${max_concurrent}"
  printf '%q ' "${command[@]}"
  printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
