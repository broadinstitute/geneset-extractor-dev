#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_cptac_models_cluster_apptainer.sh"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

CPTAC_CONFIG_ROOT="${CPTAC_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/CPTAC/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

CPTAC_STUDY_MANIFEST="${CPTAC_STUDY_MANIFEST:-${CPTAC_CONFIG_ROOT}/study_manifest.tsv}"
CPTAC_MODEL_LIST="${CPTAC_MODEL_LIST:-${CPTAC_CONFIG_ROOT}/model_list.tsv}"
CPTAC_MODEL_MANIFEST="${CPTAC_MODEL_MANIFEST:-${CPTAC_CONFIG_ROOT}/model_manifest.tsv}"

CPTAC_OUT_ROOT="${CPTAC_OUT_ROOT:-${WORK_ROOT}/cptac_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_cptac}"
CPTAC_WORKLIST="${CPTAC_WORKLIST:-${WORK_ROOT}/cptac_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  PYTHON_BIN="${APPTAINER_PYTHON_BIN}"
  PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
fi

CPTAC_ARRAY_MEMORY="${CPTAC_ARRAY_MEMORY:-16G}"
CPTAC_ARRAY_WALLTIME="${CPTAC_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-${CPTAC_CONFIG_ROOT}/model_description_templates.tsv}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
FILTER_COHORT_ID=""
FILTER_MODEL_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_cptac_models_cluster_apptainer.sh [--submit] [--write_model_only|--refresh_metadata_and_provenance] [--cohort_id COHORT] [--model_id MODEL[,MODEL...]]
  ./geneset-extractor-dev/run/submit_cptac_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS, APPTAINER_PYTHON_BIN
  CPTAC_CONFIG_ROOT, CPTAC_STUDY_MANIFEST, CPTAC_MODEL_LIST, CPTAC_MODEL_MANIFEST
  CPTAC_OUT_ROOT, QSUB_LOG_ROOT, CPTAC_WORKLIST
  CPTAC_ARRAY_MEMORY, CPTAC_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV

Notes:
  - Without --submit, the worklist is written to CPTAC_WORKLIST and the
    script exits (dry run) instead of submitting the qsub array.
  - Use --submit to actually submit the qsub array.
  - Add --write_model_only to write only geneset.model.json sidecars against
    an existing extractor/ output (skips fetch/prepare/overlay/extract).
  - Add --refresh_metadata_and_provenance to patch metadata descriptions and
    rebuild provenance for each selected model output.
  - Array tasks re-enter this script inside the Apptainer image and run the
    assigned workload row there.
  - Every enabled model in model_list.tsv is crossed with every enabled
    cohort in study_manifest.tsv (there is no all_tissues/HZ singleton).
  - No filters: one array covering all cohort x model tasks.
  - --cohort_id: one array for all enabled models for that cohort.
  - --model_id with optional --cohort_id: one array covering the selected
    model(s) (crossed with all enabled cohorts unless --cohort_id narrows it).
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
      if ($family_col == "tumor_vs_normal") print "PT"
      exit
    }
  ' "${CPTAC_MODEL_LIST}"
}

validate_model_ids() {
  local model_csv="$1"
  local requested_model_id
  IFS=',' read -r -a requested_model_ids <<< "${model_csv}"
  for requested_model_id in "${requested_model_ids[@]}"; do
    requested_model_id="${requested_model_id//[[:space:]]/}"
    [[ -n "${requested_model_id}" ]] || continue
    if [[ -z "$(resolve_model_group_for_id "${requested_model_id}")" ]]; then
      echo "Model not found in CPTAC model list: ${requested_model_id}" >&2
      exit 1
    fi
  done
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
      --cohort_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --cohort_id" >&2; exit 1; }
        FILTER_COHORT_ID="$2"
        shift 2
        ;;
      --model_id)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_id" >&2; exit 1; }
        FILTER_MODEL_IDS="$2"
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

  if [[ -n "${FILTER_MODEL_IDS}" ]]; then
    validate_model_ids "${FILTER_MODEL_IDS}"
  fi
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

  if [[ ${SUBMIT_MODE} -eq 1 && -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    require_var APPTAINER_IMAGE
    require_file "${APPTAINER_IMAGE}"
  fi
  require_file "${CPTAC_STUDY_MANIFEST}"
  require_file "${CPTAC_MODEL_LIST}"
  require_file "${CPTAC_MODEL_MANIFEST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  fi
}

write_worklist() {
  local model_tsv cohort_tsv
  model_tsv="$(mktemp)"
  cohort_tsv="$(mktemp)"
  awk -F $'\t' '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "model_id") model_id_col = i
        if ($i == "model_family") family_col = i
        if ($i == "enabled") enabled_col = i
      }
      next
    }
    enabled_col > 0 && $enabled_col == "true" {
      group = ""
      if ($family_col == "tumor_vs_normal") group = "PT"
      if (group != "") print $model_id_col "\t" group
    }
  ' "${CPTAC_MODEL_LIST}" > "${model_tsv}"

  awk -F $'\t' '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "cohort_id") cohort_id_col = i
        if ($i == "enabled") enabled_col = i
      }
      next
    }
    cohort_id_col > 0 && enabled_col > 0 && $enabled_col == "true" && $cohort_id_col != "" { print $cohort_id_col }
  ' "${CPTAC_STUDY_MANIFEST}" > "${cohort_tsv}"

  {
    printf "task_id\tcohort_id\tmodel_group\tmodel_id\n"
    awk -F $'\t' \
      -v model_tsv="${model_tsv}" \
      -v cohort_tsv="${cohort_tsv}" \
      -v filter_cohort="${FILTER_COHORT_ID}" \
      -v filter_models="${FILTER_MODEL_IDS}" '
      BEGIN {
        while ((getline line < model_tsv) > 0) {
          split(line, fields, "\t")
          n_models += 1
          model_ids[n_models] = fields[1]
          model_groups[n_models] = fields[2]
        }
        close(model_tsv)
        while ((getline line < cohort_tsv) > 0) {
          cohorts[++n_cohorts] = line
        }
        close(cohort_tsv)
        split(filter_models, requested_models, ",")
        for (requested_index in requested_models) {
          requested_model = requested_models[requested_index]
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", requested_model)
          if (requested_model != "") {
            requested_model_lookup[requested_model] = 1
          }
        }
        task_id = 0
        for (mi = 1; mi <= n_models; mi++) {
          model_id = model_ids[mi]
          model_group = model_groups[mi]
          if (filter_models != "" && !(model_id in requested_model_lookup)) continue
          for (ci = 1; ci <= n_cohorts; ci++) {
            cohort_id = cohorts[ci]
            if (filter_cohort != "" && cohort_id != filter_cohort) continue
            task_id += 1
            printf "%d\t%s\t%s\t%s\n", task_id, cohort_id, model_group, model_id
          }
        }
      }'
  } > "${CPTAC_WORKLIST}"
  rm -f "${model_tsv}" "${cohort_tsv}"

  if [[ "$(awk 'END { print NR - 1 }' "${CPTAC_WORKLIST}")" -le 0 ]]; then
    echo "CPTAC filters produced an empty worklist" >&2
    exit 1
  fi
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]] || return 0
  local filtered_worklist kept
  filtered_worklist="$(mktemp)"
  head -n 1 "${CPTAC_WORKLIST}" > "${filtered_worklist}"
  kept=0
  while IFS= read -r row; do
    [[ -n "${row}" ]] || continue
    local cohort_id model_id suffix model_dir
    IFS=$'\t' read -r _task_id cohort_id _model_group model_id <<< "${row}"
    suffix="${row#*$'\t'}"
    model_dir="${CPTAC_OUT_ROOT}/genesets/${cohort_id}/models/${model_id}"
    if [[ -d "${model_dir}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\n" "${kept}" "${suffix}" >> "${filtered_worklist}"
    fi
  done < <(tail -n +2 "${CPTAC_WORKLIST}")
  mv "${filtered_worklist}" "${CPTAC_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "CPTAC refresh filters produced an empty worklist after excluding missing outputs" >&2
    exit 1
  fi
}

prepare_worklist() {
  prepare_common
  write_worklist
  filter_refresh_existing_worklist
}

apptainer_bind_csv() {
  {
    append_bind_path "${REPO_ROOT}"
    append_bind_path "${WORK_ROOT}"
    append_bind_path "${DIG_DIR}"
    append_bind_path "${CPTAC_STUDY_MANIFEST}"
    append_bind_path "${CPTAC_MODEL_LIST}"
    append_bind_path "${CPTAC_MODEL_MANIFEST}"
    append_bind_path "${DESCRIPTION_TEMPLATE_TSV:-}"
    append_bind_path "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
    append_bind_path "${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
  } | awk '!seen[$0]++' | paste -sd, -
}

submit_array() {
  prepare_worklist

  local tasks job_name
  tasks="$(awk 'END { print NR - 1 }' "${CPTAC_WORKLIST}")"
  job_name="${CPTAC_JOB_NAME:-cptac_all_models_apptainer}"

  echo "CPTAC worklist: ${CPTAC_WORKLIST} (${tasks} tasks)"

  "${QSUB_BIN}" \
    -N "${job_name}" \
    -t "1-${tasks}" \
    -o "${QSUB_LOG_ROOT}/cptac.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/cptac.\$TASK_ID.err" \
    -l "h_vmem=${CPTAC_ARRAY_MEMORY},h_rt=${CPTAC_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},CPTAC_WORKLIST=${CPTAC_WORKLIST},CPTAC_OUT_ROOT=${CPTAC_OUT_ROOT},CPTAC_CONFIG_ROOT=${CPTAC_CONFIG_ROOT},CPTAC_STUDY_MANIFEST=${CPTAC_STUDY_MANIFEST},CPTAC_MODEL_LIST=${CPTAC_MODEL_LIST},CPTAC_MODEL_MANIFEST=${CPTAC_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV}" \
    "${SELF_PATH}"
}

write_worklist_only() {
  prepare_worklist

  local tasks
  tasks="$(awk 'END { print NR - 1 }' "${CPTAC_WORKLIST}")"
  echo "CPTAC worklist: ${CPTAC_WORKLIST} (${tasks} tasks)"
  echo "Dry run (no --submit): worklist written; nothing submitted."
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
  APPTAINERENV_CPTAC_WORKLIST="${CPTAC_WORKLIST}" \
  APPTAINERENV_CPTAC_OUT_ROOT="${CPTAC_OUT_ROOT}" \
  APPTAINERENV_CPTAC_CONFIG_ROOT="${CPTAC_CONFIG_ROOT}" \
  APPTAINERENV_CPTAC_STUDY_MANIFEST="${CPTAC_STUDY_MANIFEST}" \
  APPTAINERENV_CPTAC_MODEL_LIST="${CPTAC_MODEL_LIST}" \
  APPTAINERENV_CPTAC_MODEL_MANIFEST="${CPTAC_MODEL_MANIFEST}" \
  APPTAINERENV_DIG_DIR="${DIG_DIR}" \
  APPTAINERENV_PYTHON_BIN="${APPTAINER_PYTHON_BIN}" \
  APPTAINERENV_WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY}" \
  APPTAINERENV_REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE}" \
  APPTAINERENV_DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV}" \
  APPTAINERENV_PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX}" \
  APPTAINERENV_PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX}" \
  APPTAINERENV_LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV}" \
  "${cmd[@]}"
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then
    echo "CPTAC array-task context requires PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
  fi

  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    run_task_in_apptainer
    return
  fi

  local row cohort_id model_group model_id
  row="$(awk -F $'\t' -v target="${task_id}" 'NR > 1 && $1 == target { print; exit }' "${CPTAC_WORKLIST}")"
  if [[ -z "${row}" ]]; then
    echo "No CPTAC worklist row found for task ${task_id}" >&2
    exit 1
  fi

  IFS=$'\t' read -r _ cohort_id model_group model_id <<< "${row}"

  echo "CPTAC task ${task_id}: cohort=${cohort_id} group=${model_group} model=${model_id}"

  local model_dir
  model_dir="${CPTAC_OUT_ROOT}/genesets/${cohort_id}/models/${model_id}"

  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    local refresh_cmd
    refresh_cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${model_dir}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
      --dig_dir "${DIG_DIR}"
      --python_bin "${PYTHON_BIN}"
    )
    if [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX}" ]]; then
      refresh_cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
    fi
    if [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX}" ]]; then
      refresh_cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
    fi
    if [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV}" ]]; then
      refresh_cmd+=(--local_input_source_map_tsv "${LOCAL_INPUT_SOURCE_MAP_TSV}")
    fi
    echo "+ ${refresh_cmd[*]}"
    "${refresh_cmd[@]}"
    return
  fi

  local cmd=(
    bash "${REPO_ROOT}/geneset-extractor-dev/CPTAC/run/build_cptac_genesets.sh"
    --dig_dir "${DIG_DIR}"
    --cohort_id "${cohort_id}"
    --model_id "${model_id}"
    --out_root "${CPTAC_OUT_ROOT}"
    --config_dir "${CPTAC_CONFIG_ROOT}"
    --python_bin "${PYTHON_BIN}"
  )
  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    cmd+=(--write_model_only)
  fi
  echo "+ ${cmd[*]}"
  "${cmd[@]}"
}

main() {
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  CPTAC_OUT_ROOT="$(absolute_path "${CPTAC_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  CPTAC_WORKLIST="$(absolute_path "${CPTAC_WORKLIST}")"

  if [[ $# -eq 0 ]] && [[ -n "${PBS_ARRAYID:-}" || -n "${SGE_TASK_ID:-}" ]]; then
    run_task
    return
  fi

  parse_cli "$@"

  if [[ ${SUBMIT_MODE} -eq 1 ]]; then
    submit_array
  else
    write_worklist_only
  fi
}

main "$@"
