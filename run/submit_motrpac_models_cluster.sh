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
MOTRPAC_RAW_COUNTS_DIR="${MOTRPAC_RAW_COUNTS_DIR:-}"

MOTRPAC_OUT_ROOT="${MOTRPAC_OUT_ROOT:-${WORK_ROOT}/motrpac_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_motrpac}"
MOTRPAC_WORKLIST="${MOTRPAC_WORKLIST:-${WORK_ROOT}/motrpac_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"
QSUB_BIN="${QSUB_BIN:-qsub}"

MOTRPAC_ARRAY_MEMORY="${MOTRPAC_ARRAY_MEMORY:-16G}"
MOTRPAC_ARRAY_WALLTIME="${MOTRPAC_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE=0
FILTER_MODEL_GROUP=""
FILTER_TISSUE_ID=""
FILTER_MODEL_ID=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_motrpac_models_cluster.sh --submit [--model_group TW|HZ] [--tissue_id TISSUE|all_tissues] [--model_id MODEL]
  ./geneset-extractor-dev/run/submit_motrpac_models_cluster.sh --help

Required environment variables:
  MOTRPAC_RAW_COUNTS_DIR
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
  - No filters: one array covering all tissue+model tasks.
  - --model_group: one array for all tasks in that group.
  - --tissue_id: one array for all models for that tissue.
  - --model_id with optional --tissue_id: one single-task submission.
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

canonicalize_model_group() {
  case "$1" in
    TW|timewise) printf '%s\n' "TW" ;;
    HZ|hz_released_dea) printf '%s\n' "HZ" ;;
    TR|training) printf '%s\n' "TR" ;;
    *) return 1 ;;
  esac
}

resolve_model_group_for_id() {
  local model_id="$1"
  awk -F $'\t' -v model_id="${model_id}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "model_id") model_id_col = i
        if ($i == "model_family") family_col = i
      }
      next
    }
    $model_id_col == model_id {
      if ($family_col == "timewise") print "TW"
      else if ($family_col == "hz_released_dea") print "HZ"
      else if ($family_col == "training") print "TR"
      exit
    }
  ' "${MOTRPAC_MODEL_LIST}"
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit)
        SUBMIT_MODE=1
        shift
        ;;
      --model_group)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_group" >&2; exit 1; }
        FILTER_MODEL_GROUP="$(canonicalize_model_group "$2")" || {
          echo "Unsupported MoTrPAC model group: $2" >&2
          exit 1
        }
        shift 2
        ;;
      --tissue_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --tissue_id" >&2; exit 1; }
        FILTER_TISSUE_ID="$2"
        shift 2
        ;;
      --model_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_id" >&2; exit 1; }
        FILTER_MODEL_ID="$2"
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

  if [[ -n "${FILTER_MODEL_ID}" ]]; then
    local derived_group
    derived_group="$(resolve_model_group_for_id "${FILTER_MODEL_ID}")"
    if [[ -z "${derived_group}" ]]; then
      echo "Model not found in MoTrPAC model list: ${FILTER_MODEL_ID}" >&2
      exit 1
    fi
    if [[ -n "${FILTER_MODEL_GROUP}" && "${FILTER_MODEL_GROUP}" != "${derived_group}" ]]; then
      echo "--model_id ${FILTER_MODEL_ID} conflicts with --model_group ${FILTER_MODEL_GROUP}" >&2
      exit 1
    fi
    FILTER_MODEL_GROUP="${derived_group}"
    if [[ "${derived_group}" == "HZ" && -z "${FILTER_TISSUE_ID}" ]]; then
      FILTER_TISSUE_ID="all_tissues"
    fi
    if [[ "${derived_group}" != "HZ" && -z "${FILTER_TISSUE_ID}" ]]; then
      echo "--model_id ${FILTER_MODEL_ID} requires --tissue_id for non-HZ MoTrPAC models" >&2
      exit 1
    fi
  fi

  if [[ ${SUBMIT_MODE} -ne 1 ]]; then
    usage
    exit 1
  fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

  require_var MOTRPAC_TRANSCRIPT_METADATA_TSV
  require_var MOTRPAC_PHENOTYPE_METADATA_TSV
  require_var MOTRPAC_FEATURE_TO_GENE_TSV
  require_var MOTRPAC_RAT_TO_HUMAN_TSV
  require_var MOTRPAC_RAW_COUNTS_DIR
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
  require_dir "${MOTRPAC_RAW_COUNTS_DIR}"
  require_file "${MOTRPAC_FEATURE_ANNOT}"
  require_dir "${MOTRPAC_DEA_DIR}"
  require_file "${MOTRPAC_MAPPING_FILE}"
}

write_worklist() {
  local model_tsv tissue_tsv
  model_tsv="$(mktemp)"
  tissue_tsv="$(mktemp)"
  awk -F $'\t' 'NR > 1 && $4 == "true" {
    group = ""
    if ($2 == "timewise") group = "TW"
    else if ($2 == "hz_released_dea") group = "HZ"
    else if ($2 == "training") group = "TR"
    if (group != "") print $1 "\t" group
  }' "${MOTRPAC_MODEL_LIST}" > "${model_tsv}"
  awk -F $'\t' '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "tissue_id") tissue_id_col = i
      }
      next
    }
    tissue_id_col > 0 && $tissue_id_col != "" { print $tissue_id_col }
  ' "${MOTRPAC_TISSUE_LIST}" > "${tissue_tsv}"

  {
    printf "task_id\ttissue_id\tmodel_group\tmodel_id\n"
    awk -F $'\t' \
      -v model_tsv="${model_tsv}" \
      -v tissue_tsv="${tissue_tsv}" \
      -v filter_group="${FILTER_MODEL_GROUP}" \
      -v filter_tissue="${FILTER_TISSUE_ID}" \
      -v filter_model="${FILTER_MODEL_ID}" '
      BEGIN {
        while ((getline line < model_tsv) > 0) {
          split(line, fields, "\t")
          n_models += 1
          model_ids[n_models] = fields[1]
          model_groups[n_models] = fields[2]
        }
        close(model_tsv)
        while ((getline line < tissue_tsv) > 0) {
          tissues[++n_tissues] = line
        }
        close(tissue_tsv)
        task_id = 0
        for (mi = 1; mi <= n_models; mi++) {
          model_id = model_ids[mi]
          model_group = model_groups[mi]
          if (filter_group != "" && model_group != filter_group) continue
          if (model_group == "HZ") {
            tissue_id = "all_tissues"
            if (filter_tissue != "" && tissue_id != filter_tissue) continue
            if (filter_model != "" && model_id != filter_model) continue
            task_id += 1
            printf "%d\t%s\t%s\t%s\n", task_id, tissue_id, model_group, model_id
          } else {
            for (ti = 1; ti <= n_tissues; ti++) {
              tissue_id = tissues[ti]
              if (filter_tissue != "" && tissue_id != filter_tissue) continue
              if (filter_model != "" && model_id != filter_model) continue
              task_id += 1
              printf "%d\t%s\t%s\t%s\n", task_id, tissue_id, model_group, model_id
            }
          }
        }
      }'
  } > "${MOTRPAC_WORKLIST}"
  rm -f "${model_tsv}" "${tissue_tsv}"

  if [[ "$(awk 'END { print NR - 1 }' "${MOTRPAC_WORKLIST}")" -le 0 ]]; then
    echo "MoTrPAC filters produced an empty worklist" >&2
    exit 1
  fi
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
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},MOTRPAC_WORKLIST=${MOTRPAC_WORKLIST},MOTRPAC_OUT_ROOT=${MOTRPAC_OUT_ROOT},MOTRPAC_MODEL_LIST=${MOTRPAC_MODEL_LIST},MOTRPAC_TISSUE_LIST=${MOTRPAC_TISSUE_LIST},MOTRPAC_MODEL_MANIFEST=${MOTRPAC_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},RSCRIPT_BIN=${RSCRIPT_BIN},MOTRPAC_RAW_COUNTS_DIR=${MOTRPAC_RAW_COUNTS_DIR},MOTRPAC_TRANSCRIPT_METADATA_TSV=${MOTRPAC_TRANSCRIPT_METADATA_TSV},MOTRPAC_PHENOTYPE_METADATA_TSV=${MOTRPAC_PHENOTYPE_METADATA_TSV},MOTRPAC_FEATURE_TO_GENE_TSV=${MOTRPAC_FEATURE_TO_GENE_TSV},MOTRPAC_RAT_TO_HUMAN_TSV=${MOTRPAC_RAT_TO_HUMAN_TSV},MOTRPAC_FEATURE_ANNOT=${MOTRPAC_FEATURE_ANNOT},MOTRPAC_DEA_DIR=${MOTRPAC_DEA_DIR},MOTRPAC_MAPPING_FILE=${MOTRPAC_MAPPING_FILE}" \
    "${BASH_SOURCE[0]}"
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then
    echo "MoTrPAC worker requires PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  fi

  local row tissue_id model_group model_id
  row="$(awk -F $'\t' -v target="${task_id}" 'NR > 1 && $1 == target { print; exit }' "${MOTRPAC_WORKLIST}")"
  if [[ -z "${row}" ]]; then
    echo "No MoTrPAC worklist row found for task ${task_id}" >&2
    exit 1
  fi

  IFS=$'\t' read -r _ tissue_id model_group model_id <<< "${row}"

  echo "MoTrPAC task ${task_id}: tissue=${tissue_id} group=${model_group} model=${model_id}"

  local cmd=(
    bash "${REPO_ROOT}/geneset-extractor-dev/MoTrPAC/run/build_motrpac_genesets.sh"
    --models "${model_id}"
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
      --raw_counts_dir "${MOTRPAC_RAW_COUNTS_DIR}"
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

  parse_cli "$@"
  submit_array
}

main "$@"
