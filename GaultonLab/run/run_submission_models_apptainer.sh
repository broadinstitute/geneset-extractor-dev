#!/usr/bin/env bash
set -euo pipefail

mode="${1:---full}"; shift || true
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: $0 [--smoke|--full] [--models HZ1[,HZ2,HZ3]] [--partitions heart[,liver,lung,spleen]]" >&2; exit 2 ;; esac
[[ "${mode}" == "full" ]] && mode="--full"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
workspace_root="$(cd -- "${root}/../.." && pwd -P)"
source_dir="${GAULTONLAB_GMT_DIR:-${workspace_root}/submissions/cfde_legacy/GaultonLab}"
input_map="${GAULTONLAB_GMT_MAP_TSV:-}"

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  export PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
  export GAULTONLAB_GMT_DIR="${source_dir}"
  export GAULTONLAB_GMT_MAP_TSV="${input_map}"
  exec bash "${root}/run/run_submission_models.sh" "${mode}" --out-root "${SUBMISSION_WORK_DIR}" "$@"
fi

[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the checkout" >&2; exit 1; }
if [[ -z "${input_map}" ]]; then
  [[ -d "${source_dir}" ]] || { echo "GAULTONLAB_GMT_DIR must identify the supplied GMT directory" >&2; exit 1; }
fi
if [[ -n "${input_map}" ]]; then
  [[ -f "${input_map}" ]] || { echo "GAULTONLAB_GMT_MAP_TSV must identify an input-map TSV" >&2; exit 1; }
fi
mkdir -p "${SUBMISSION_WORK_DIR}"

bind_paths=("${root}" "${DIG_REPO}" "${SUBMISSION_WORK_DIR}")
[[ -d "${source_dir}" ]] && bind_paths+=("${source_dir}")
if [[ -n "${input_map}" ]]; then
  bind_paths+=("$(cd -- "$(dirname -- "${input_map}")" && pwd -P)")
  while IFS= read -r input_path; do
    [[ -n "${input_path}" ]] || continue
    [[ "${input_path}" == /* ]] || input_path="$(cd -- "$(dirname -- "${input_map}")" && pwd -P)/${input_path}"
    [[ -f "${input_path}" ]] || { echo "Input GMT listed in ${input_map} is missing: ${input_path}" >&2; exit 1; }
    bind_paths+=("$(cd -- "$(dirname -- "${input_path}")" && pwd -P)")
  done < <(awk -F $'\t' 'NR == 1 { for (i = 1; i <= NF; i++) if ($i == "input_gmt") col = i; next } col && $col != "" { print $col }' "${input_map}")
fi
bind_csv="$(IFS=,; printf '%s' "${bind_paths[*]}")"

exec "${APPTAINER_BIN:-apptainer}" exec \
  --bind "${bind_csv}" \
  "${APPTAINER_IMAGE}" env \
  GENESET_EXTRACTORS_IN_APPTAINER=1 \
  APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" \
  DIG_REPO="${DIG_REPO}" \
  SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
  GAULTONLAB_GMT_DIR="${source_dir}" \
  GAULTONLAB_GMT_MAP_TSV="${input_map}" \
  bash "${root}/run/run_submission_models_apptainer.sh" "${mode}" "$@"
