#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

SCRNA_CONFIG_ROOT="${SCRNA_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/scRNA_cNMF/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

SCRNA_MODEL_LIST="${SCRNA_MODEL_LIST:-${SCRNA_CONFIG_ROOT}/model_list.tsv}"
SCRNA_MODEL_MANIFEST="${SCRNA_MODEL_MANIFEST:-${SCRNA_CONFIG_ROOT}/model_manifest.tsv}"
SCRNA_DATASET_LIST="${SCRNA_DATASET_LIST:-${SCRNA_CONFIG_ROOT}/dataset_list.tsv}"

SCRNA_OUT_ROOT="${SCRNA_OUT_ROOT:-${WORK_ROOT}/scrna_cnmf_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_scrna_cnmf}"
SCRNA_WORKLIST="${SCRNA_WORKLIST:-${WORK_ROOT}/scrna_cnmf_qsub_worklist.tsv}"

# Input map TSV: columns dataset_id, matrix_tsv, meta_tsv
SCRNA_INPUT_MAP_TSV="${SCRNA_INPUT_MAP_TSV:-}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"

SCRNA_ARRAY_MEMORY="${SCRNA_ARRAY_MEMORY:-32G}"
SCRNA_ARRAY_WALLTIME="${SCRNA_ARRAY_WALLTIME:-48:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
FILTER_MODEL_IDS=""
FILTER_DATASET_IDS=""

usage() {
  cat <<'EOF'
Usage:
  submit_scrna_cnmf_models_cluster.sh --submit [--write_model_only|--refresh_metadata_and_provenance]
      [--model_id MODEL[,MODEL...]] [--dataset_id DATASET[,DATASET...]]
  submit_scrna_cnmf_models_cluster.sh --help

Required environment variables (for --submit without --write_model_only or --refresh):
  SCRNA_INPUT_MAP_TSV   (TSV with columns: dataset_id, matrix_tsv, meta_tsv)

Optional environment variables:
  REPO_ROOT, WORK_ROOT
  SCRNA_OUT_ROOT, QSUB_LOG_ROOT, SCRNA_WORKLIST
  SCRNA_CONFIG_ROOT, DIG_DIR
  PYTHON_BIN, QSUB_BIN
  SCRNA_ARRAY_MEMORY, SCRNA_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV
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

absolute_path() {
  local path="$1"
  if [[ "${path}" == /* ]]; then
    printf '%s\n' "${path}"
  else
    printf '%s/%s\n' "$(pwd)" "${path}"
  fi
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit)
        SUBMIT_MODE=1
        shift
        ;;
      --write_model_only)
        WRITE_MODEL_ONLY=1
        shift
        ;;
      --refresh_metadata_and_provenance)
        REFRESH_METADATA_AND_PROVENANCE=1
        shift
        ;;
      --model_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_id" >&2; exit 1; }
        FILTER_MODEL_IDS="$2"
        shift 2
        ;;
      --dataset_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --dataset_id" >&2; exit 1; }
        FILTER_DATASET_IDS="$2"
        shift 2
        ;;
      -h|--help|help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done

  if [[ ${WRITE_MODEL_ONLY} -eq 1 && ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    echo "Use only one of --write_model_only or --refresh_metadata_and_provenance" >&2
    exit 1
  fi

  if [[ ${SUBMIT_MODE} -ne 1 ]]; then
    usage
    exit 1
  fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"
  require_file "${SCRNA_MODEL_LIST}"
  require_file "${SCRNA_MODEL_MANIFEST}"
  require_file "${SCRNA_DATASET_LIST}"

  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  elif [[ ${WRITE_MODEL_ONLY} -eq 0 ]]; then
    require_var SCRNA_INPUT_MAP_TSV
    require_file "${SCRNA_INPUT_MAP_TSV}"
  fi
}

write_worklist() {
  {
    printf "task_id\tdataset_id\tmodel_id\n"
    awk -F $'\t' \
      -v filter_models="${FILTER_MODEL_IDS}" \
      -v filter_datasets="${FILTER_DATASET_IDS}" \
      -v dataset_list="${SCRNA_DATASET_LIST}" \
      '
      BEGIN {
        split(filter_models, fm, ",")
        for (i in fm) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", fm[i]); if (fm[i] != "") model_filter[fm[i]] = 1 }
        split(filter_datasets, fd, ",")
        for (i in fd) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", fd[i]); if (fd[i] != "") dataset_filter[fd[i]] = 1 }

        while ((getline line < dataset_list) > 0) {
          if (line ~ /^dataset_id/) {
            split(line, dh, "\t")
            for (i = 1; i <= length(dh); i++) if (dh[i] == "dataset_id") dcol_id = i
            for (i = 1; i <= length(dh); i++) if (dh[i] == "enabled") dcol_en = i
            continue
          }
          split(line, dr, "\t")
          did = dr[dcol_id]; den = dr[dcol_en]
          if (den == "true") enabled_datasets[did] = 1
        }
        close(dataset_list)
      }
      NR == 1 {
        for (i = 1; i <= NF; i++) {
          if ($i == "model_id") model_id_col = i
          if ($i == "enabled") enabled_col = i
        }
        next
      }
      $enabled_col == "true" {
        model_id = $model_id_col
        if (length(model_filter) > 0 && !(model_id in model_filter)) next
        for (did in enabled_datasets) {
          if (length(dataset_filter) > 0 && !(did in dataset_filter)) continue
          task_id += 1
          printf "%d\t%s\t%s\n", task_id, did, model_id
        }
      }
    ' "${SCRNA_MODEL_LIST}"
  } > "${SCRNA_WORKLIST}"
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]] || return 0
  local filtered_worklist kept
  filtered_worklist="$(mktemp)"
  head -n 1 "${SCRNA_WORKLIST}" > "${filtered_worklist}"
  kept=0
  while IFS=$'\t' read -r _task_id dataset_id model_id; do
    [[ -n "${model_id}" ]] || continue
    local model_dir
    model_dir="${SCRNA_OUT_ROOT}/genesets/${dataset_id}/models/${model_id}"
    if [[ -d "${model_dir}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\t%s\n" "${kept}" "${dataset_id}" "${model_id}" >> "${filtered_worklist}"
    fi
  done < <(tail -n +2 "${SCRNA_WORKLIST}")
  mv "${filtered_worklist}" "${SCRNA_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "No scRNA cNMF refresh tasks selected (no extractor/ dirs found)." >&2
    exit 1
  fi
}

worklist_task_count() {
  awk 'NR > 1 { n += 1 } END { print n + 0 }' "${SCRNA_WORKLIST}"
}

task_id_from_env() {
  if [[ -n "${PBS_ARRAYID:-}" ]]; then
    printf '%s\n' "${PBS_ARRAYID}"
    return
  fi
  if [[ -n "${SGE_TASK_ID:-}" ]]; then
    printf '%s\n' "${SGE_TASK_ID}"
    return
  fi
  return 1
}

lookup_input_paths() {
  local dataset_id="$1"
  local matrix_tsv meta_tsv
  matrix_tsv="$(awk -F $'\t' -v did="${dataset_id}" 'NR==1{for(i=1;i<=NF;i++){if($i=="dataset_id")dc=i; if($i=="matrix_tsv")mc=i}} NR>1&&$dc==did{print $mc;exit}' "${SCRNA_INPUT_MAP_TSV}")"
  meta_tsv="$(awk -F $'\t' -v did="${dataset_id}" 'NR==1{for(i=1;i<=NF;i++){if($i=="dataset_id")dc=i; if($i=="meta_tsv")ec=i}} NR>1&&$dc==did{print $ec;exit}' "${SCRNA_INPUT_MAP_TSV}")"
  if [[ -z "${matrix_tsv}" || -z "${meta_tsv}" ]]; then
    echo "Dataset '${dataset_id}' not found in SCRNA_INPUT_MAP_TSV: ${SCRNA_INPUT_MAP_TSV}" >&2
    exit 1
  fi
  printf '%s\t%s\n' "${matrix_tsv}" "${meta_tsv}"
}

run_worker() {
  local task_id dataset_id model_id
  task_id="$(task_id_from_env)" || {
    echo "Unable to determine array task id from PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  }
  IFS=$'\t' read -r _tid dataset_id model_id < <(
    awk -F $'\t' -v tid="${task_id}" 'NR>1 && $1==tid {print $0; exit}' "${SCRNA_WORKLIST}"
  )
  if [[ -z "${model_id:-}" ]]; then
    echo "No scRNA cNMF worklist row for task_id=${task_id}" >&2
    exit 1
  fi

  local src_root
  src_root="${REPO_ROOT}/geneset-extractor-dev/scRNA_cNMF/src"
  local cmd

  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/run_scrna_cnmf_model.py"
      "--model_id" "${model_id}"
      "--dataset_id" "${dataset_id}"
      "--run_root" "${SCRNA_OUT_ROOT}/genesets"
      "--matrix_tsv" "/dev/null"
      "--meta_tsv" "/dev/null"
      "--python_bin" "${PYTHON_BIN}"
      "--dig_dir" "${DIG_DIR}"
      "--model_manifest" "${SCRNA_MODEL_MANIFEST}"
      "--dataset_list" "${SCRNA_DATASET_LIST}"
      "--write_model_only"
    )
  elif [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${SCRNA_OUT_ROOT}/genesets/${dataset_id}/models/${model_id}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
      --python_bin "${PYTHON_BIN}"
      --dig_dir "${DIG_DIR}"
    )
    if [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]]; then
      cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
    fi
    if [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]]; then
      cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
    fi
    if [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV:-}" ]]; then
      cmd+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}")
    fi
  else
    local input_line matrix_tsv meta_tsv
    input_line="$(lookup_input_paths "${dataset_id}")"
    matrix_tsv="$(printf '%s' "${input_line}" | cut -f1)"
    meta_tsv="$(printf '%s' "${input_line}" | cut -f2)"
    cmd=(
      "${PYTHON_BIN}"
      "${src_root}/run_scrna_cnmf_model.py"
      "--model_id" "${model_id}"
      "--dataset_id" "${dataset_id}"
      "--run_root" "${SCRNA_OUT_ROOT}/genesets"
      "--matrix_tsv" "${matrix_tsv}"
      "--meta_tsv" "${meta_tsv}"
      "--python_bin" "${PYTHON_BIN}"
      "--dig_dir" "${DIG_DIR}"
      "--model_manifest" "${SCRNA_MODEL_MANIFEST}"
      "--dataset_list" "${SCRNA_DATASET_LIST}"
    )
    if [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}" ]]; then
      cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
    fi
    if [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX:-}" ]]; then
      cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
    fi
    if [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV:-}" ]]; then
      cmd+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}")
    fi
  fi

  printf '$'
  printf ' %q' "${cmd[@]}"
  printf '\n'
  "${cmd[@]}"
}

submit_array() {
  write_worklist
  filter_refresh_existing_worklist
  local task_count
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then
    echo "No scRNA cNMF tasks selected." >&2
    exit 1
  fi

  echo "Submitting ${task_count} scRNA cNMF task(s) from ${SCRNA_WORKLIST}" >&2

  "${QSUB_BIN}" \
    -N "scrna_cnmf_all_models" \
    -t "1-${task_count}" \
    -o "${QSUB_LOG_ROOT}/scrna_cnmf.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/scrna_cnmf.\$TASK_ID.err" \
    -l "h_vmem=${SCRNA_ARRAY_MEMORY},h_rt=${SCRNA_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},SCRNA_WORKLIST=${SCRNA_WORKLIST},SCRNA_OUT_ROOT=${SCRNA_OUT_ROOT},SCRNA_MODEL_LIST=${SCRNA_MODEL_LIST},SCRNA_MODEL_MANIFEST=${SCRNA_MODEL_MANIFEST},SCRNA_DATASET_LIST=${SCRNA_DATASET_LIST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV},SCRNA_INPUT_MAP_TSV=${SCRNA_INPUT_MAP_TSV:-}" \
    "${REPO_ROOT}/geneset-extractor-dev/run/submit_scrna_cnmf_models_cluster.sh"
}

main() {
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  SCRNA_OUT_ROOT="$(absolute_path "${SCRNA_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  SCRNA_WORKLIST="$(absolute_path "${SCRNA_WORKLIST}")"

  if [[ $# -eq 0 ]] && task_id_from_env >/dev/null 2>&1; then
    prepare_common
    run_worker
  else
    parse_cli "$@"
    prepare_common
    submit_array
  fi
}

main "$@"
