#!/usr/bin/env bash
# Run one existing HZ4 cell-line × perturbation-time task inside Apptainer.
set -euo pipefail

task_id=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id) task_id="${2:-}"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if [[ -z "${task_id}" ]]; then
  task_id="${SGE_TASK_ID:-}"
fi
[[ -n "${task_id}" ]] || { echo "--task-id is required outside an SGE array" >&2; exit 2; }
if [[ -n "${LINCS_L1000_ROOT:-}" ]]; then
  root="$(cd -- "${LINCS_L1000_ROOT}" && pwd -P)"
else
  root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
fi
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
[[ -n "${LINCS_CP_COEFF_GCTX:-}" && -f "${LINCS_CP_COEFF_GCTX}" ]] || { echo "Set LINCS_CP_COEFF_GCTX to cp_coeff_mat.gctx" >&2; exit 1; }
plan_dir="${HZ4_PARTITION_PLAN_DIR:-${SUBMISSION_WORK_DIR}/genesets/hz4_cell_line_time_plan}"
[[ -f "${plan_dir}/task_manifest.tsv" ]] || { echo "Missing HZ4 task manifest: ${plan_dir}/task_manifest.tsv" >&2; exit 1; }
if [[ "${task_id}" =~ ^[0-9]+$ ]]; then
  task_id="$(awk -F $'\t' -v task_number="${task_id}" 'NR == task_number + 1 { print $1 }' "${plan_dir}/task_manifest.tsv")"
  [[ -n "${task_id}" ]] || { echo "No HZ4 task at the requested array index" >&2; exit 1; }
fi

declare -A bind_paths=()
add_bind_path() {
  local path="$1"
  if [[ -f "${path}" ]]; then path="$(cd -- "$(dirname -- "${path}")" && pwd -P)"; else path="$(cd -- "${path}" && pwd -P)"; fi
  bind_paths["${path}"]=1
}
add_bind_path "${root}"
add_bind_path "${DIG_REPO}"
add_bind_path "${SUBMISSION_WORK_DIR}"
add_bind_path "${LINCS_CP_COEFF_GCTX}"
binds="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"
overwrite_args=()
if [[ "${HZ4_OVERWRITE:-0}" == "1" ]]; then
  overwrite_args=(--overwrite)
fi

exec "${APPTAINER_BIN:-apptainer}" exec ${APPTAINER_EXTRA_ARGS:-} --bind "${binds}" "${APPTAINER_IMAGE}" \
  python3 "${root}/src/build_lincs_l1000_genesets.py" \
  --models HZ4 --dig_dir "${DIG_REPO}" --cp_coeff_gctx "${LINCS_CP_COEFF_GCTX}" \
  --out_root "${SUBMISSION_WORK_DIR}" --hz4_partition_mode cell_line_time \
  --hz4_partition_plan_dir "${plan_dir}" --hz4_task_id "${task_id}" "${overwrite_args[@]}"
