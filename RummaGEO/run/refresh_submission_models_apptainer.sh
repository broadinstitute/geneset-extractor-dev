#!/usr/bin/env bash
# Refresh RummaGEO model metadata and provenance inside Apptainer.
set -euo pipefail

models="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --models) [[ $# -ge 2 ]] || { echo "Missing value for --models" >&2; exit 2; }; models="$2"; shift 2 ;;
    --models=*) models="${1#--models=}"; shift ;;
    -h|--help) echo "usage: refresh_submission_models_apptainer.sh [--models HZ1[,HZ2]]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
dev_root="$(cd -- "${root}/.." && pwd -P)"
description_template_tsv="${DESCRIPTION_TEMPLATE_TSV:-${root}/config/model_description_templates.tsv}"
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a dig-gene-set-extractors checkout" >&2; exit 1; }
[[ -f "${description_template_tsv}" ]] || { echo "Missing DESCRIPTION_TEMPLATE_TSV: ${description_template_tsv}" >&2; exit 1; }

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  IFS=',' read -r -a model_ids <<< "${models}"
  if [[ "${models}" == "all" ]]; then model_ids=(HZ1 HZ2); fi
  for model_id in "${model_ids[@]}"; do
    model_id="${model_id//[[:space:]]/}"
    model_dir="${SUBMISSION_WORK_DIR}/genesets/all_signatures/models/${model_id}"
    [[ -d "${model_dir}" ]] || { echo "Missing RummaGEO model output: ${model_dir}" >&2; exit 1; }
    command=(bash "${dev_root}/run/refresh_model_metadata_and_provenance.sh" --model_id "${model_id}" --model_dir "${model_dir}" --description_template_tsv "${description_template_tsv}" --python_bin "${APPTAINER_PYTHON_BIN:-python}")
    [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]] && command+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
    [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]] && command+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
    [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV:-}" ]] && command+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}")
    printf '$ '; printf '%q ' "${command[@]}"; printf '\n'
    DIG_DIR="${DIG_REPO}" PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" "${command[@]}"
  done
  exit 0
fi

[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
declare -A bind_paths=()
add_bind_path() {
  local path="$1"
  [[ -n "${path}" ]] || return
  if [[ -f "${path}" ]]; then path="$(cd -- "$(dirname -- "${path}")" && pwd -P)"; else path="$(cd -- "${path}" && pwd -P)"; fi
  bind_paths["${path}"]=1
}
add_bind_path "${dev_root}"
add_bind_path "${DIG_REPO}"
add_bind_path "${SUBMISSION_WORK_DIR}"
add_bind_path "${description_template_tsv}"
add_bind_path "${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
add_bind_path "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
bind_csv="$(printf '%s\n' "${!bind_paths[@]}" | paste -sd, -)"
extra_args=()
if [[ -n "${APPTAINER_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=(${APPTAINER_EXTRA_ARGS})
fi

APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
APPTAINERENV_APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}" \
APPTAINERENV_DIG_REPO="${DIG_REPO}" \
APPTAINERENV_SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
APPTAINERENV_DESCRIPTION_TEMPLATE_TSV="${description_template_tsv}" \
APPTAINERENV_LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}" \
APPTAINERENV_PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" \
APPTAINERENV_PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" \
"${APPTAINER_BIN:-apptainer}" exec --bind "${bind_csv}" "${extra_args[@]}" "${APPTAINER_IMAGE}" \
  bash "${root}/run/refresh_submission_models_apptainer.sh" --models "${models}"
