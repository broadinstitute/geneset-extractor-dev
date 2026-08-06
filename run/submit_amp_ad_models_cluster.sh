#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORK_ROOT="${WORK_ROOT:-$(cd "${WRAPPER_ROOT}/.." && pwd)}"

AMP_AD_CONFIG_ROOT="${AMP_AD_CONFIG_ROOT:-${WRAPPER_ROOT}/AMP_AD/config}"
DIG_DIR="${DIG_DIR:-${WORK_ROOT}/dig-gene-set-extractors}"
AMP_AD_MODEL_LIST="${AMP_AD_MODEL_LIST:-${AMP_AD_CONFIG_ROOT}/model_list.tsv}"
AMP_AD_MODEL_MANIFEST="${AMP_AD_MODEL_MANIFEST:-${AMP_AD_CONFIG_ROOT}/model_manifest.tsv}"
AMP_AD_INPUT_TSV="${AMP_AD_INPUT_TSV:-}"
AMP_AD_OUT_ROOT="${AMP_AD_OUT_ROOT:-${WORK_ROOT}/amp_ad_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_amp_ad}"
AMP_AD_WORKLIST="${AMP_AD_WORKLIST:-${WORK_ROOT}/amp_ad_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"
AMP_AD_ARRAY_MEMORY="${AMP_AD_ARRAY_MEMORY:-8G}"
AMP_AD_ARRAY_WALLTIME="${AMP_AD_ARRAY_WALLTIME:-08:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
FILTER_MODEL_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_amp_ad_models_cluster.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--model_id MODEL[,MODEL...]]

Required environment variables:
  AMP_AD_INPUT_TSV

Optional environment variables:
  WORK_ROOT, DIG_DIR, PYTHON_BIN, QSUB_BIN
  AMP_AD_OUT_ROOT, QSUB_LOG_ROOT, AMP_AD_WORKLIST
  AMP_AD_ARRAY_MEMORY, AMP_AD_ARRAY_WALLTIME
EOF
}

require_file() {
  [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit) SUBMIT_MODE=1; shift ;;
      --write_model_only) WRITE_MODEL_ONLY=1; shift ;;
      --refresh_metadata_and_provenance) REFRESH_METADATA_AND_PROVENANCE=1; shift ;;
      --model_id) FILTER_MODEL_IDS="$2"; shift 2 ;;
      -h|--help|help) usage; exit 0 ;;
      *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
  done
}

model_enabled() {
  local model_id="$1"
  awk -F $'\t' -v model_id="${model_id}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "model_id") model_col = i
        if ($i == "enabled") enabled_col = i
      }
      next
    }
    $model_col == model_id && $enabled_col == "true" { found = 1 }
    END { exit found ? 0 : 1 }
  ' "${AMP_AD_MODEL_LIST}"
}

write_worklist() {
  mkdir -p "$(dirname "${AMP_AD_WORKLIST}")" "${QSUB_LOG_ROOT}"
  printf 'model_id\tmode\n' > "${AMP_AD_WORKLIST}"
  local models
  if [[ -n "${FILTER_MODEL_IDS}" ]]; then
    models="${FILTER_MODEL_IDS}"
  else
    models="$(awk -F $'\t' 'NR == 1 {for (i=1;i<=NF;i++){if($i=="model_id")m=i;if($i=="enabled")e=i}; next} $e=="true"{print $m}' "${AMP_AD_MODEL_LIST}" | paste -sd, -)"
  fi
  IFS=',' read -r -a model_ids <<< "${models}"
  local model_id
  for model_id in "${model_ids[@]}"; do
    model_id="${model_id//[[:space:]]/}"
    [[ -n "${model_id}" ]] || continue
    model_enabled "${model_id}" || { echo "Model is not enabled or not found: ${model_id}" >&2; exit 1; }
    if [[ "${REFRESH_METADATA_AND_PROVENANCE}" == "1" ]]; then
      printf '%s\trefresh\n' "${model_id}" >> "${AMP_AD_WORKLIST}"
    else
      printf '%s\tbuild\n' "${model_id}" >> "${AMP_AD_WORKLIST}"
    fi
  done
}

run_worklist_row() {
  local row="${SGE_TASK_ID:-1}"
  local model_id mode
  model_id="$(awk -F $'\t' -v row="${row}" 'NR == row + 1 {print $1}' "${AMP_AD_WORKLIST}")"
  mode="$(awk -F $'\t' -v row="${row}" 'NR == row + 1 {print $2}' "${AMP_AD_WORKLIST}")"
  [[ -n "${model_id}" ]] || { echo "No worklist row for SGE_TASK_ID=${row}" >&2; exit 1; }
  require_file "${AMP_AD_INPUT_TSV}"
  if [[ "${mode}" == "refresh" ]]; then
    "${PYTHON_BIN}" "${WRAPPER_ROOT}/src/refresh_model_metadata_and_provenance.py" \
      --model_id "${model_id}" \
      --model_dir "${AMP_AD_OUT_ROOT}/genesets/all_brain/models/${model_id}" \
      --description_template_tsv "${AMP_AD_CONFIG_ROOT}/model_description_templates.tsv" \
      --dig_dir "${DIG_DIR}"
  else
    "${PYTHON_BIN}" "${WRAPPER_ROOT}/AMP_AD/src/run_amp_ad_model.py" \
      --model_id "${model_id}" \
      --input_tsv "${AMP_AD_INPUT_TSV}" \
      --run_root "${AMP_AD_OUT_ROOT}/genesets/all_brain/models" \
      --dig_dir "${DIG_DIR}" \
      --model_manifest "${AMP_AD_MODEL_MANIFEST}" \
      ${WRITE_MODEL_ONLY:+--write_model_only}
  fi
}

parse_cli "$@"
require_file "${AMP_AD_MODEL_LIST}"
require_file "${AMP_AD_MODEL_MANIFEST}"

if [[ -n "${SGE_TASK_ID:-}" ]]; then
  run_worklist_row
  exit 0
fi

write_worklist
if [[ "${SUBMIT_MODE}" != "1" ]]; then
  echo "Wrote worklist: ${AMP_AD_WORKLIST}"
  exit 0
fi

n_tasks=$(( $(wc -l < "${AMP_AD_WORKLIST}") - 1 ))
[[ "${n_tasks}" -gt 0 ]] || { echo "No AMP_AD tasks selected" >&2; exit 1; }
"${QSUB_BIN}" -cwd -V -j y -o "${QSUB_LOG_ROOT}" -l "h_vmem=${AMP_AD_ARRAY_MEMORY}" -l "h_rt=${AMP_AD_ARRAY_WALLTIME}" -t "1-${n_tasks}" "$0"
