#!/usr/bin/env bash
# Create HZ4 cell-line × perturbation-time worklists inside the Apptainer image.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the LINCS_L1000 checkout" >&2; exit 1; }
[[ -n "${LINCS_CP_COEFF_GCTX:-}" && -f "${LINCS_CP_COEFF_GCTX}" ]] || { echo "Set LINCS_CP_COEFF_GCTX to cp_coeff_mat.gctx" >&2; exit 1; }

plan_dir="${HZ4_PARTITION_PLAN_DIR:-${SUBMISSION_WORK_DIR}/genesets/hz4_cell_line_time_plan}"
max_signatures="${HZ4_MAX_SIGNATURES_PER_TASK:-10000}"
mkdir -p "${SUBMISSION_WORK_DIR}" "${plan_dir}"

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

exec "${APPTAINER_BIN:-apptainer}" exec ${APPTAINER_EXTRA_ARGS:-} --bind "${binds}" "${APPTAINER_IMAGE}" \
  python3 "${root}/src/build_lincs_l1000_genesets.py" \
  --models HZ4 --dig_dir "${DIG_REPO}" --cp_coeff_gctx "${LINCS_CP_COEFF_GCTX}" \
  --out_root "${SUBMISSION_WORK_DIR}" --hz4_partition_mode cell_line_time \
  --hz4_partition_plan_dir "${plan_dir}" --hz4_max_signatures_per_task "${max_signatures}"
