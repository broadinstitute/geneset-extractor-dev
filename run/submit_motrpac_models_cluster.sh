#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

MOTRPAC_CONFIG_ROOT="${MOTRPAC_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/MoTrPAC/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

MOTRPAC_MODEL_LIST="${MOTRPAC_MODEL_LIST:-${MOTRPAC_CONFIG_ROOT}/model_list.tsv}"
MOTRPAC_TISSUE_LIST="${MOTRPAC_TISSUE_LIST:-${MOTRPAC_CONFIG_ROOT}/tissue_list.tsv}"
MOTRPAC_MODEL_MANIFEST="${MOTRPAC_MODEL_MANIFEST:-${MOTRPAC_CONFIG_ROOT}/model_manifest.tsv}"

MOTRPAC_OUT_ROOT="${MOTRPAC_OUT_ROOT:-${WORK_ROOT}/motrpac_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_motrpac}"
MOTRPAC_WORKLIST="${MOTRPAC_WORKLIST:-${WORK_ROOT}/motrpac_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"
QSUB_BIN="${QSUB_BIN:-qsub}"

MOTRPAC_ARRAY_MEMORY="${MOTRPAC_ARRAY_MEMORY:-16G}"
MOTRPAC_ARRAY_WALLTIME="${MOTRPAC_ARRAY_WALLTIME:-24:00:00}"

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_motrpac_models_cluster.sh --submit
  ./geneset-extractor-dev/run/submit_motrpac_models_cluster.sh --help

Required environment variables:
  MOTRPAC_TRANSCRIPT_METADATA_TSV
  MOTRPAC_PHENOTYPE_METADATA_TSV
  MOTRPAC_FEATURE_TO_GENE_TSV
  MOTRPAC_RAT_TO_HUMAN_TSV
  MOTRPAC_FEATURE_ANNOT
  MOTRPAC_DEA_DIR
  MOTRPAC_MAPPING_FILE

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, RSCRIPT_BIN, QSUB_BIN
  MOTRPAC_OUT_ROOT, QSUB_LOG_ROOT, MOTRPAC_WORKLIST
  MOTRPAC_ARRAY_MEMORY, MOTRPAC_ARRAY_WALLTIME

Notes:
  - Use --submit to submit the qsub array.
  - When run inside a qsub array task, it auto-detects the task context and
    runs the assigned workload row.
EOF
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

require_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "Missing required file: ${path}" >&2
    exit 1
  fi
}

require_dir() {
  local path="$1"
  if [[ ! -d "${path}" ]]; then
    echo "Missing required directory: ${path}" >&2
    exit 1
  fi
}

csv_from_tsv_filter() {
  local tsv_path="$1"
  local family_col="$2"
  local family_value="$3"
  awk -F $'\t' -v family_col="${family_col}" -v family_value="${family_value}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "model_id") model_id_col = i
        if ($i == family_col) family_idx = i
        if ($i == "enabled") enabled_col = i
      }
      next
    }
    $family_idx == family_value && $enabled_col == "true" { print $model_id_col }
  ' "${tsv_path}" | paste -sd, -
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  require_var MOTRPAC_TRANSCRIPT_METADATA_TSV
  require_var MOTRPAC_PHENOTYPE_METADATA_TSV
  require_var MOTRPAC_FEATURE_TO_GENE_TSV
  require_var MOTRPAC_RAT_TO_HUMAN_TSV
  require_var MOTRPAC_FEATURE_ANNOT
  require_var MOTRPAC_DEA_DIR
  require_var MOTRPAC_MAPPING_FILE

  require_file "${MOTRPAC_MODEL_LIST}"
  require_file "${MOTRPAC_TISSUE_LIST}"
  require_file "${MOTRPAC_MODEL_MANIFEST}"
  require_file "${MOTRPAC_TRANSCRIPT_METADATA_TSV}"
  require_file "${MOTRPAC_PHENOTYPE_METADATA_TSV}"
  require_file "${MOTRPAC_FEATURE_TO_GENE_TSV}"
  require_file "${MOTRPAC_RAT_TO_HUMAN_TSV}"
  require_file "${MOTRPAC_FEATURE_ANNOT}"
  require_dir "${MOTRPAC_DEA_DIR}"
  require_file "${MOTRPAC_MAPPING_FILE}"
}

write_worklist() {
  local tw_models hz_models
  tw_models="$(csv_from_tsv_filter "${MOTRPAC_MODEL_LIST}" "model_family" "timewise")"
  hz_models="$(csv_from_tsv_filter "${MOTRPAC_MODEL_LIST}" "model_family" "hz_released_dea")"

  if [[ -z "${tw_models}" || -z "${hz_models}" ]]; then
    echo "Failed to resolve MoTrPAC model families from ${MOTRPAC_MODEL_LIST}" >&2
    exit 1
  fi

  {
    printf "task_id\ttissue_id\tmodel_group\tmodels\n"
    awk -F $'\t' -v tw="${tw_models}" '
      BEGIN { task_id = 0 }
      NR == 1 { next }
      $5 == "true" {
        task_id += 1
        printf "%d\t%s\tTW\t%s\n", task_id, $1, tw
      }
    ' "${MOTRPAC_TISSUE_LIST}"
    printf "1000000000\tall_tissues\tHZ\t%s\n" "${hz_models}"
  } > "${MOTRPAC_WORKLIST}"
}

submit_array() {
  prepare_common
  write_worklist

  local tasks job_name
  tasks="$(awk 'END { print NR - 1 }' "${MOTRPAC_WORKLIST}")"
  job_name="${MOTRPAC_JOB_NAME:-motrpac_all_models}"

  echo "MoTrPAC worklist: ${MOTRPAC_WORKLIST} (${tasks} tasks)"

  "${QSUB_BIN}" \
    -N "${job_name}" \
    -t "1-${tasks}" \
    -o "${QSUB_LOG_ROOT}/motrpac.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/motrpac.\$TASK_ID.err" \
    -l "h_vmem=${MOTRPAC_ARRAY_MEMORY},h_rt=${MOTRPAC_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},MOTRPAC_WORKLIST=${MOTRPAC_WORKLIST},MOTRPAC_OUT_ROOT=${MOTRPAC_OUT_ROOT},MOTRPAC_MODEL_LIST=${MOTRPAC_MODEL_LIST},MOTRPAC_TISSUE_LIST=${MOTRPAC_TISSUE_LIST},MOTRPAC_MODEL_MANIFEST=${MOTRPAC_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},RSCRIPT_BIN=${RSCRIPT_BIN},MOTRPAC_TRANSCRIPT_METADATA_TSV=${MOTRPAC_TRANSCRIPT_METADATA_TSV},MOTRPAC_PHENOTYPE_METADATA_TSV=${MOTRPAC_PHENOTYPE_METADATA_TSV},MOTRPAC_FEATURE_TO_GENE_TSV=${MOTRPAC_FEATURE_TO_GENE_TSV},MOTRPAC_RAT_TO_HUMAN_TSV=${MOTRPAC_RAT_TO_HUMAN_TSV},MOTRPAC_FEATURE_ANNOT=${MOTRPAC_FEATURE_ANNOT},MOTRPAC_DEA_DIR=${MOTRPAC_DEA_DIR},MOTRPAC_MAPPING_FILE=${MOTRPAC_MAPPING_FILE}" \
    "${BASH_SOURCE[0]}"
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then
    echo "MoTrPAC worker requires PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  fi

  local row tissue_id model_group models
  row="$(awk -F $'\t' -v target="${task_id}" 'NR > 1 && $1 == target { print; exit }' "${MOTRPAC_WORKLIST}")"
  if [[ -z "${row}" ]]; then
    echo "No MoTrPAC worklist row found for task ${task_id}" >&2
    exit 1
  fi

  IFS=$'\t' read -r _ tissue_id model_group models <<< "${row}"

  echo "MoTrPAC task ${task_id}: tissue=${tissue_id} group=${model_group} models=${models}"

  local cmd=(
    bash "${REPO_ROOT}/geneset-extractor-dev/MoTrPAC/run/build_motrpac_genesets.sh"
    --models "${models}"
    --model_list "${MOTRPAC_MODEL_LIST}"
    --tissue_list "${MOTRPAC_TISSUE_LIST}"
    --model_manifest "${MOTRPAC_MODEL_MANIFEST}"
    --dig_dir "${DIG_DIR}"
    --python_bin "${PYTHON_BIN}"
    --rscript_bin "${RSCRIPT_BIN}"
    --out_root "${MOTRPAC_OUT_ROOT}"
    --overwrite
  )

  if [[ "${model_group}" == "TW" ]]; then
    cmd+=(
      --tissues "${tissue_id}"
      --transcript_metadata_tsv "${MOTRPAC_TRANSCRIPT_METADATA_TSV}"
      --phenotype_metadata_tsv "${MOTRPAC_PHENOTYPE_METADATA_TSV}"
      --feature_to_gene_tsv "${MOTRPAC_FEATURE_TO_GENE_TSV}"
      --rat_to_human_tsv "${MOTRPAC_RAT_TO_HUMAN_TSV}"
    )
  elif [[ "${model_group}" == "HZ" ]]; then
    cmd+=(
      --feature_annot "${MOTRPAC_FEATURE_ANNOT}"
      --dea_dir "${MOTRPAC_DEA_DIR}"
      --mapping_file "${MOTRPAC_MAPPING_FILE}"
    )
  else
    echo "Unsupported MoTrPAC model group: ${model_group}" >&2
    exit 1
  fi

  echo "+ ${cmd[*]}"
  "${cmd[@]}"
}

main() {
  local mode="${1:-}"
  if [[ -n "${PBS_ARRAYID:-}" || -n "${SGE_TASK_ID:-}" ]]; then
    if [[ -n "${mode}" ]]; then
      echo "Unexpected argument in array-task mode: ${mode}" >&2
      exit 1
    fi
    run_task
    return
  fi

  case "${mode}" in
    --submit)
      submit_array
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      echo "Unknown mode: ${mode}" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
