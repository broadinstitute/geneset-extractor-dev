#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_gtex_models_cluster_apptainer.sh"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

GTEX_CONFIG_ROOT="${GTEX_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/GTEx/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

GTEX_MODEL_LIST="${GTEX_MODEL_LIST:-${GTEX_CONFIG_ROOT}/model_list.tsv}"
GTEX_BROAD_TISSUE_LIST="${GTEX_BROAD_TISSUE_LIST:-${GTEX_CONFIG_ROOT}/broad_tissue_list.tsv}"
GTEX_AGE_BINNED_MODEL_MANIFEST="${GTEX_AGE_BINNED_MODEL_MANIFEST:-${GTEX_CONFIG_ROOT}/age_binned_model_manifest.tsv}"
GTEX_CONTINUOUS_AGE_MODEL_MANIFEST="${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST:-${GTEX_CONFIG_ROOT}/continuous_age_model_manifest.tsv}"

GTEX_OUT_ROOT="${GTEX_OUT_ROOT:-${WORK_ROOT}/gtex_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_gtex}"
GTEX_WORKLIST="${GTEX_WORKLIST:-${WORK_ROOT}/gtex_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"
QSUB_BIN="${QSUB_BIN:-qsub}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"

GTEX_ARRAY_MEMORY="${GTEX_ARRAY_MEMORY:-16G}"
GTEX_ARRAY_WALLTIME="${GTEX_ARRAY_WALLTIME:-24:00:00}"

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_gtex_models_cluster_apptainer.sh --submit
  ./geneset-extractor-dev/run/submit_gtex_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE
  GTEX_V10_COUNTS_GCT
  GTEX_V10_SAMPLE_ATTRIBUTES_TSV
  GTEX_V10_SUBJECT_PHENOTYPES_TSV
  GTEX_V8_COUNTS_GCT
  GTEX_V8_SAMPLE_ATTRIBUTES_TSV
  GTEX_V8_SUBJECT_PHENOTYPES_TSV
  GTEX_V8_HUMAN_GENE_INFO
  GTEX_GTF

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, RSCRIPT_BIN, QSUB_BIN
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS
  GTEX_OUT_ROOT, QSUB_LOG_ROOT, GTEX_WORKLIST
  GTEX_ARRAY_MEMORY, GTEX_ARRAY_WALLTIME

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
  require_var GTEX_V10_COUNTS_GCT
  require_var GTEX_V10_SAMPLE_ATTRIBUTES_TSV
  require_var GTEX_V10_SUBJECT_PHENOTYPES_TSV
  require_var GTEX_V8_COUNTS_GCT
  require_var GTEX_V8_SAMPLE_ATTRIBUTES_TSV
  require_var GTEX_V8_SUBJECT_PHENOTYPES_TSV
  require_var GTEX_V8_HUMAN_GENE_INFO
  require_var GTEX_GTF

  require_file "${APPTAINER_IMAGE}"
  require_file "${GTEX_MODEL_LIST}"
  require_file "${GTEX_BROAD_TISSUE_LIST}"
  require_file "${GTEX_AGE_BINNED_MODEL_MANIFEST}"
  require_file "${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST}"
  require_file "${GTEX_V10_COUNTS_GCT}"
  require_file "${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}"
  require_file "${GTEX_V10_SUBJECT_PHENOTYPES_TSV}"
  require_file "${GTEX_V8_COUNTS_GCT}"
  require_file "${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}"
  require_file "${GTEX_V8_SUBJECT_PHENOTYPES_TSV}"
  require_file "${GTEX_V8_HUMAN_GENE_INFO}"
  require_file "${GTEX_GTF}"
}

write_worklist() {
  local ab_models ac_models hz_models
  ab_models="$(csv_from_tsv_filter "${GTEX_MODEL_LIST}" "model_family" "age_binned")"
  ac_models="$(csv_from_tsv_filter "${GTEX_MODEL_LIST}" "model_family" "continuous_age")"
  hz_models="$(csv_from_tsv_filter "${GTEX_MODEL_LIST}" "model_family" "hz_notebook")"

  if [[ -z "${ab_models}" || -z "${ac_models}" || -z "${hz_models}" ]]; then
    echo "Failed to resolve GTEx model families from ${GTEX_MODEL_LIST}" >&2
    exit 1
  fi

  {
    printf "task_id\ttissue_id\tmodel_group\tmodels\tcounts_gct\tsample_metadata_tsv\tsubject_metadata_tsv\thuman_gene_info\tgtf\n"
    awk -F $'\t' -v ab="${ab_models}" -v ac="${ac_models}" -v hz="${hz_models}" \
      -v v10_counts="${GTEX_V10_COUNTS_GCT}" \
      -v v10_sample="${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}" \
      -v v10_subject="${GTEX_V10_SUBJECT_PHENOTYPES_TSV}" \
      -v v8_counts="${GTEX_V8_COUNTS_GCT}" \
      -v v8_sample="${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}" \
      -v v8_subject="${GTEX_V8_SUBJECT_PHENOTYPES_TSV}" \
      -v v8_hgi="${GTEX_V8_HUMAN_GENE_INFO}" \
      -v gtf="${GTEX_GTF}" '
      BEGIN { task_id = 0 }
      NR == 1 { next }
      {
        task_id += 1
        printf "%d\t%s\tAB\t%s\t%s\t%s\t%s\t\t%s\n", task_id, $1, ab, v10_counts, v10_sample, v10_subject, gtf
        task_id += 1
        printf "%d\t%s\tAC\t%s\t%s\t%s\t%s\t\t%s\n", task_id, $1, ac, v10_counts, v10_sample, v10_subject, gtf
        task_id += 1
        printf "%d\t%s\tHZ\t%s\t%s\t%s\t%s\t%s\t%s\n", task_id, $1, hz, v8_counts, v8_sample, v8_subject, v8_hgi, gtf
      }
    ' "${GTEX_BROAD_TISSUE_LIST}"
  } > "${GTEX_WORKLIST}"
}

apptainer_bind_csv() {
  {
    append_bind_path "${REPO_ROOT}"
    append_bind_path "${WORK_ROOT}"
    append_bind_path "${DIG_DIR}"
    append_bind_path "${GTEX_MODEL_LIST}"
    append_bind_path "${GTEX_BROAD_TISSUE_LIST}"
    append_bind_path "${GTEX_AGE_BINNED_MODEL_MANIFEST}"
    append_bind_path "${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST}"
    append_bind_path "${GTEX_V10_COUNTS_GCT}"
    append_bind_path "${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}"
    append_bind_path "${GTEX_V10_SUBJECT_PHENOTYPES_TSV}"
    append_bind_path "${GTEX_V8_COUNTS_GCT}"
    append_bind_path "${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}"
    append_bind_path "${GTEX_V8_SUBJECT_PHENOTYPES_TSV}"
    append_bind_path "${GTEX_V8_HUMAN_GENE_INFO}"
    append_bind_path "${GTEX_GTF}"
  } | awk '!seen[$0]++' | paste -sd, -
}

submit_array() {
  prepare_common
  write_worklist

  local tasks job_name
  tasks="$(awk 'END { print NR - 1 }' "${GTEX_WORKLIST}")"
  job_name="${GTEX_JOB_NAME:-gtex_all_models_apptainer}"

  echo "GTEx worklist: ${GTEX_WORKLIST} (${tasks} tasks)"

  "${QSUB_BIN}" \
    -N "${job_name}" \
    -t "1-${tasks}" \
    -o "${QSUB_LOG_ROOT}/gtex.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/gtex.\$TASK_ID.err" \
    -l "h_vmem=${GTEX_ARRAY_MEMORY},h_rt=${GTEX_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},GTEX_WORKLIST=${GTEX_WORKLIST},GTEX_OUT_ROOT=${GTEX_OUT_ROOT},GTEX_MODEL_LIST=${GTEX_MODEL_LIST},GTEX_BROAD_TISSUE_LIST=${GTEX_BROAD_TISSUE_LIST},GTEX_AGE_BINNED_MODEL_MANIFEST=${GTEX_AGE_BINNED_MODEL_MANIFEST},GTEX_CONTINUOUS_AGE_MODEL_MANIFEST=${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},RSCRIPT_BIN=${RSCRIPT_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},GTEX_V10_COUNTS_GCT=${GTEX_V10_COUNTS_GCT},GTEX_V10_SAMPLE_ATTRIBUTES_TSV=${GTEX_V10_SAMPLE_ATTRIBUTES_TSV},GTEX_V10_SUBJECT_PHENOTYPES_TSV=${GTEX_V10_SUBJECT_PHENOTYPES_TSV},GTEX_V8_COUNTS_GCT=${GTEX_V8_COUNTS_GCT},GTEX_V8_SAMPLE_ATTRIBUTES_TSV=${GTEX_V8_SAMPLE_ATTRIBUTES_TSV},GTEX_V8_SUBJECT_PHENOTYPES_TSV=${GTEX_V8_SUBJECT_PHENOTYPES_TSV},GTEX_V8_HUMAN_GENE_INFO=${GTEX_V8_HUMAN_GENE_INFO},GTEX_GTF=${GTEX_GTF}" \
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
  APPTAINERENV_GTEX_WORKLIST="${GTEX_WORKLIST}" \
  APPTAINERENV_GTEX_OUT_ROOT="${GTEX_OUT_ROOT}" \
  APPTAINERENV_GTEX_MODEL_LIST="${GTEX_MODEL_LIST}" \
  APPTAINERENV_GTEX_BROAD_TISSUE_LIST="${GTEX_BROAD_TISSUE_LIST}" \
  APPTAINERENV_GTEX_AGE_BINNED_MODEL_MANIFEST="${GTEX_AGE_BINNED_MODEL_MANIFEST}" \
  APPTAINERENV_GTEX_CONTINUOUS_AGE_MODEL_MANIFEST="${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST}" \
  APPTAINERENV_DIG_DIR="${DIG_DIR}" \
  APPTAINERENV_PYTHON_BIN="${PYTHON_BIN}" \
  APPTAINERENV_RSCRIPT_BIN="${RSCRIPT_BIN}" \
  APPTAINERENV_GTEX_V10_COUNTS_GCT="${GTEX_V10_COUNTS_GCT}" \
  APPTAINERENV_GTEX_V10_SAMPLE_ATTRIBUTES_TSV="${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}" \
  APPTAINERENV_GTEX_V10_SUBJECT_PHENOTYPES_TSV="${GTEX_V10_SUBJECT_PHENOTYPES_TSV}" \
  APPTAINERENV_GTEX_V8_COUNTS_GCT="${GTEX_V8_COUNTS_GCT}" \
  APPTAINERENV_GTEX_V8_SAMPLE_ATTRIBUTES_TSV="${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}" \
  APPTAINERENV_GTEX_V8_SUBJECT_PHENOTYPES_TSV="${GTEX_V8_SUBJECT_PHENOTYPES_TSV}" \
  APPTAINERENV_GTEX_V8_HUMAN_GENE_INFO="${GTEX_V8_HUMAN_GENE_INFO}" \
  APPTAINERENV_GTEX_GTF="${GTEX_GTF}" \
  "${cmd[@]}"
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then
    echo "GTEx array-task context requires PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  fi

  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    run_task_in_apptainer
    return
  fi

  local row tissue_id model_group models counts_gct sample_tsv subject_tsv human_gene_info gtf
  row="$(awk -F $'\t' -v target="${task_id}" 'NR > 1 && $1 == target { print; exit }' "${GTEX_WORKLIST}")"
  if [[ -z "${row}" ]]; then
    echo "No GTEx worklist row found for task ${task_id}" >&2
    exit 1
  fi

  IFS=$'\t' read -r _ tissue_id model_group models counts_gct sample_tsv subject_tsv human_gene_info gtf <<< "${row}"

  echo "GTEx task ${task_id}: tissue=${tissue_id} group=${model_group} models=${models}"

  local cmd=(
    bash "${REPO_ROOT}/geneset-extractor-dev/GTEx/run/build_genesets.sh"
    --tissue_granularity broad
    --tissues "${tissue_id}"
    --models "${models}"
    --counts_gct "${counts_gct}"
    --sample_metadata_tsv "${sample_tsv}"
    --subject_metadata_tsv "${subject_tsv}"
    --model_list "${GTEX_MODEL_LIST}"
    --broad_tissue_list "${GTEX_BROAD_TISSUE_LIST}"
    --dig_dir "${DIG_DIR}"
    --python_bin "${PYTHON_BIN}"
    --rscript_bin "${RSCRIPT_BIN}"
    --out_root "${GTEX_OUT_ROOT}"
    --gtf "${GTEX_GTF}"
    --overwrite
  )

  if [[ "${model_group}" == "AB" ]]; then
    cmd+=(--age_binned_model_manifest "${GTEX_AGE_BINNED_MODEL_MANIFEST}")
  elif [[ "${model_group}" == "AC" ]]; then
    cmd+=(--continuous_age_model_manifest "${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST}")
  elif [[ "${model_group}" == "HZ" ]]; then
    cmd+=(--human_gene_info "${human_gene_info}")
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
