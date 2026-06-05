#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_motrpac_models_cluster_apptainer.sh"
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
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"

MOTRPAC_ARRAY_MEMORY="${MOTRPAC_ARRAY_MEMORY:-16G}"
MOTRPAC_ARRAY_WALLTIME="${MOTRPAC_ARRAY_WALLTIME:-24:00:00}"

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_motrpac_models_cluster_apptainer.sh --submit
  ./geneset-extractor-dev/run/submit_motrpac_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE
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
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS
  MOTRPAC_OUT_ROOT, QSUB_LOG_ROOT, MOTRPAC_WORKLIST
  MOTRPAC_ARRAY_MEMORY, MOTRPAC_ARRAY_WALLTIME

Notes:
  - Use --submit to submit the qsub array.
  - Array tasks re-enter this script inside the Apptainer image and run the
    assigned workload row there.
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

append_bind_path() {
  local path="$1"
  if [[ -z "${path}" ]]; then
    return
  fi
  if [[ -d "${path}" ]]; then
    printf '%s\n' "${path}"
  elif [[ -e "${path}" ]]; then
    dirname "${path}"
  fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  require_var APPTAINER_IMAGE
  require_var MOTRPAC_TRANSCRIPT_METADATA_TSV
  require_var MOTRPAC_PHENOTYPE_METADATA_TSV
  require_var MOTRPAC_FEATURE_TO_GENE_TSV
  require_var MOTRPAC_RAT_TO_HUMAN_TSV
  require_var MOTRPAC_FEATURE_ANNOT
  require_var MOTRPAC_DEA_DIR
  require_var MOTRPAC_MAPPING_FILE

  require_file "${APPTAINER_IMAGE}"
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

apptainer_bind_csv() {
  {
    append_bind_path "${REPO_ROOT}"
    append_bind_path "${WORK_ROOT}"
    append_bind_path "${DIG_DIR}"
    append_bind_path "${MOTRPAC_MODEL_LIST}"
    append_bind_path "${MOTRPAC_TISSUE_LIST}"
    append_bind_path "${MOTRPAC_MODEL_MANIFEST}"
    append_bind_path "${MOTRPAC_TRANSCRIPT_METADATA_TSV}"
    append_bind_path "${MOTRPAC_PHENOTYPE_METADATA_TSV}"
    append_bind_path "${MOTRPAC_FEATURE_TO_GENE_TSV}"
    append_bind_path "${MOTRPAC_RAT_TO_HUMAN_TSV}"
    append_bind_path "${MOTRPAC_FEATURE_ANNOT}"
    append_bind_path "${MOTRPAC_DEA_DIR}"
    append_bind_path "${MOTRPAC_MAPPING_FILE}"
  } | awk '!seen[$0]++' | paste -sd, -
}

submit_array() {
  prepare_common
  write_worklist

  local tasks job_name
  tasks="$(awk 'END { print NR - 1 }' "${MOTRPAC_WORKLIST}")"
  job_name="${MOTRPAC_JOB_NAME:-motrpac_all_models_apptainer}"

  echo "MoTrPAC worklist: ${MOTRPAC_WORKLIST} (${tasks} tasks)"

  "${QSUB_BIN}" \
    -N "${job_name}" \
    -t "1-${tasks}" \
    -o "${QSUB_LOG_ROOT}/motrpac.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/motrpac.\$TASK_ID.err" \
    -l "h_vmem=${MOTRPAC_ARRAY_MEMORY},h_rt=${MOTRPAC_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},MOTRPAC_WORKLIST=${MOTRPAC_WORKLIST},MOTRPAC_OUT_ROOT=${MOTRPAC_OUT_ROOT},MOTRPAC_MODEL_LIST=${MOTRPAC_MODEL_LIST},MOTRPAC_TISSUE_LIST=${MOTRPAC_TISSUE_LIST},MOTRPAC_MODEL_MANIFEST=${MOTRPAC_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},RSCRIPT_BIN=${RSCRIPT_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},MOTRPAC_TRANSCRIPT_METADATA_TSV=${MOTRPAC_TRANSCRIPT_METADATA_TSV},MOTRPAC_PHENOTYPE_METADATA_TSV=${MOTRPAC_PHENOTYPE_METADATA_TSV},MOTRPAC_FEATURE_TO_GENE_TSV=${MOTRPAC_FEATURE_TO_GENE_TSV},MOTRPAC_RAT_TO_HUMAN_TSV=${MOTRPAC_RAT_TO_HUMAN_TSV},MOTRPAC_FEATURE_ANNOT=${MOTRPAC_FEATURE_ANNOT},MOTRPAC_DEA_DIR=${MOTRPAC_DEA_DIR},MOTRPAC_MAPPING_FILE=${MOTRPAC_MAPPING_FILE}" \
    "${SELF_PATH}"
}

run_task_in_apptainer() {
  local bind_csv
  bind_csv="$(apptainer_bind_csv)"
  local -a cmd
  cmd=("${APPTAINER_BIN}" exec --bind "${bind_csv}")
  if [[ -n "${APPTAINER_EXTRA_ARGS}" ]]; then
    # shellcheck disable=SC2206
    cmd+=(${APPTAINER_EXTRA_ARGS})
  fi
  cmd+=("${APPTAINER_IMAGE}" bash "${SELF_PATH}")

  echo "+ GENESET_EXTRACTORS_IN_APPTAINER=1 ${cmd[*]}"
  APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 \
  APPTAINERENV_PBS_ARRAYID="${PBS_ARRAYID:-}" \
  APPTAINERENV_SGE_TASK_ID="${SGE_TASK_ID:-}" \
  APPTAINERENV_REPO_ROOT="${REPO_ROOT}" \
  APPTAINERENV_WORK_ROOT="${WORK_ROOT}" \
  APPTAINERENV_MOTRPAC_WORKLIST="${MOTRPAC_WORKLIST}" \
  APPTAINERENV_MOTRPAC_OUT_ROOT="${MOTRPAC_OUT_ROOT}" \
  APPTAINERENV_MOTRPAC_MODEL_LIST="${MOTRPAC_MODEL_LIST}" \
  APPTAINERENV_MOTRPAC_TISSUE_LIST="${MOTRPAC_TISSUE_LIST}" \
  APPTAINERENV_MOTRPAC_MODEL_MANIFEST="${MOTRPAC_MODEL_MANIFEST}" \
  APPTAINERENV_DIG_DIR="${DIG_DIR}" \
  APPTAINERENV_PYTHON_BIN="${PYTHON_BIN}" \
  APPTAINERENV_RSCRIPT_BIN="${RSCRIPT_BIN}" \
  APPTAINERENV_MOTRPAC_TRANSCRIPT_METADATA_TSV="${MOTRPAC_TRANSCRIPT_METADATA_TSV}" \
  APPTAINERENV_MOTRPAC_PHENOTYPE_METADATA_TSV="${MOTRPAC_PHENOTYPE_METADATA_TSV}" \
  APPTAINERENV_MOTRPAC_FEATURE_TO_GENE_TSV="${MOTRPAC_FEATURE_TO_GENE_TSV}" \
  APPTAINERENV_MOTRPAC_RAT_TO_HUMAN_TSV="${MOTRPAC_RAT_TO_HUMAN_TSV}" \
  APPTAINERENV_MOTRPAC_FEATURE_ANNOT="${MOTRPAC_FEATURE_ANNOT}" \
  APPTAINERENV_MOTRPAC_DEA_DIR="${MOTRPAC_DEA_DIR}" \
  APPTAINERENV_MOTRPAC_MAPPING_FILE="${MOTRPAC_MAPPING_FILE}" \
  "${cmd[@]}"
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then
    echo "MoTrPAC array-task context requires PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  fi

  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    run_task_in_apptainer
    return
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
