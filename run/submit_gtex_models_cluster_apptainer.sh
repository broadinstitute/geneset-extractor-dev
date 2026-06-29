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
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
APPTAINER_RSCRIPT_BIN="${APPTAINER_RSCRIPT_BIN:-Rscript}"

if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  PYTHON_BIN="${APPTAINER_PYTHON_BIN}"
  RSCRIPT_BIN="${APPTAINER_RSCRIPT_BIN}"
  PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
  RSCRIPT_BIN="$(command -v "${RSCRIPT_BIN}")"
fi

GTEX_ARRAY_MEMORY="${GTEX_ARRAY_MEMORY:-16G}"
GTEX_ARRAY_WALLTIME="${GTEX_ARRAY_WALLTIME:-24:00:00}"
GTEX_V10_COUNTS_GCT="${GTEX_V10_COUNTS_GCT:-}"
GTEX_V10_SAMPLE_ATTRIBUTES_TSV="${GTEX_V10_SAMPLE_ATTRIBUTES_TSV:-}"
GTEX_V10_SUBJECT_PHENOTYPES_TSV="${GTEX_V10_SUBJECT_PHENOTYPES_TSV:-}"
GTEX_V8_COUNTS_GCT="${GTEX_V8_COUNTS_GCT:-}"
GTEX_V8_SAMPLE_ATTRIBUTES_TSV="${GTEX_V8_SAMPLE_ATTRIBUTES_TSV:-}"
GTEX_V8_SUBJECT_PHENOTYPES_TSV="${GTEX_V8_SUBJECT_PHENOTYPES_TSV:-}"
GTEX_V8_HUMAN_GENE_INFO="${GTEX_V8_HUMAN_GENE_INFO:-}"
GTEX_GTF="${GTEX_GTF:-}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
FILTER_MODEL_GROUP=""
FILTER_TISSUE_ID=""
FILTER_MODEL_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_gtex_models_cluster_apptainer.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--model_group AB|AC|HZ] [--tissue_id TISSUE] [--model_id MODEL[,MODEL...]]
  ./geneset-extractor-dev/run/submit_gtex_models_cluster_apptainer.sh --help

Required environment variables:
  APPTAINER_IMAGE

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, RSCRIPT_BIN, QSUB_BIN
  APPTAINER_BIN, APPTAINER_EXTRA_ARGS
  APPTAINER_PYTHON_BIN, APPTAINER_RSCRIPT_BIN
  GTEX_OUT_ROOT, QSUB_LOG_ROOT, GTEX_WORKLIST
  GTEX_ARRAY_MEMORY, GTEX_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV

Notes:
  - Use --submit to submit the qsub array.
  - Add --write_model_only to write only geneset.model.json sidecars.
  - Add --refresh_metadata_and_provenance to patch metadata descriptions and
    rebuild provenance for each selected model output.
  - Full workflow runs require GTEX_V10_*, GTEX_V8_*, GTEX_V8_HUMAN_GENE_INFO,
    and GTEX_GTF. Model-only runs do not.
  - Array tasks re-enter this script inside the Apptainer image and run the
    assigned workload row there.
  - No filters: one array covering all tissue+model tasks.
  - --model_group: one array for all tissue+model tasks in that group.
  - --tissue_id: one array for all models for that tissue.
  - --model_id alone: one array for the selected model(s) across all tissues.
  - --model_id plus --tissue_id: one array covering the selected model(s) for that tissue.
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
    AB|age_binned) printf '%s\n' "AB" ;;
    AC|continuous_age) printf '%s\n' "AC" ;;
    HZ|hz_notebook) printf '%s\n' "HZ" ;;
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
      if ($family_col == "age_binned") print "AB"
      else if ($family_col == "continuous_age") print "AC"
      else if ($family_col == "hz_notebook") print "HZ"
      exit
    }
  ' "${GTEX_MODEL_LIST}"
}

validate_model_ids() {
  local model_csv="$1"
  local requested_model_id
  local -A seen_groups=()
  IFS=',' read -r -a requested_model_ids <<< "${model_csv}"
  for requested_model_id in "${requested_model_ids[@]}"; do
    requested_model_id="${requested_model_id//[[:space:]]/}"
    [[ -n "${requested_model_id}" ]] || continue
    local derived_group
    derived_group="$(resolve_model_group_for_id "${requested_model_id}")"
    if [[ -z "${derived_group}" ]]; then
      echo "Model not found in GTEx model list: ${requested_model_id}" >&2
      exit 1
    fi
    if [[ -n "${FILTER_MODEL_GROUP}" && "${FILTER_MODEL_GROUP}" != "${derived_group}" ]]; then
      echo "--model_id ${requested_model_id} conflicts with --model_group ${FILTER_MODEL_GROUP}" >&2
      exit 1
    fi
    seen_groups["${derived_group}"]=1
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
      --model_group)
        [[ $# -ge 2 ]] || { echo "Missing value for --model_group" >&2; exit 1; }
        FILTER_MODEL_GROUP="$(canonicalize_model_group "$2")" || {
          echo "Unsupported GTEx model group: $2" >&2
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

  if [[ ${SUBMIT_MODE} -ne 1 ]]; then
    usage
    exit 1
  fi
}

resolve_tissue_label() {
  local tissue_id="$1"
  awk -F $'\t' -v tissue_id="${tissue_id}" '
    NR == 1 {
      for (i = 1; i <= NF; i++) {
        if ($i == "tissue_id") tissue_id_col = i
        if ($i == "tissue_name") tissue_name_col = i
      }
      next
    }
    $tissue_id_col == tissue_id {
      print $tissue_name_col
      exit
    }
  ' "${GTEX_BROAD_TISSUE_LIST}"
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

  if [[ -z "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
    require_var APPTAINER_IMAGE
    require_file "${APPTAINER_IMAGE}"
  fi
  require_file "${GTEX_MODEL_LIST}"
  require_file "${GTEX_BROAD_TISSUE_LIST}"
  require_file "${GTEX_AGE_BINNED_MODEL_MANIFEST}"
  require_file "${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    require_file "${DESCRIPTION_TEMPLATE_TSV}"
  fi
  if [[ ${WRITE_MODEL_ONLY} -ne 1 && ${REFRESH_METADATA_AND_PROVENANCE} -ne 1 ]]; then
    require_var GTEX_V10_COUNTS_GCT
    require_var GTEX_V10_SAMPLE_ATTRIBUTES_TSV
    require_var GTEX_V10_SUBJECT_PHENOTYPES_TSV
    require_var GTEX_V8_COUNTS_GCT
    require_var GTEX_V8_SAMPLE_ATTRIBUTES_TSV
    require_var GTEX_V8_SUBJECT_PHENOTYPES_TSV
    require_var GTEX_V8_HUMAN_GENE_INFO
    require_var GTEX_GTF
    require_file "${GTEX_V10_COUNTS_GCT}"
    require_file "${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}"
    require_file "${GTEX_V10_SUBJECT_PHENOTYPES_TSV}"
    require_file "${GTEX_V8_COUNTS_GCT}"
    require_file "${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}"
    require_file "${GTEX_V8_SUBJECT_PHENOTYPES_TSV}"
    require_file "${GTEX_V8_HUMAN_GENE_INFO}"
    require_file "${GTEX_GTF}"
  fi
}

write_worklist() {
  local model_tsv tissue_tsv
  model_tsv="$(mktemp)"
  tissue_tsv="$(mktemp)"
  awk -F $'\t' 'NR > 1 && $3 == "true" {
    group = ""
    if ($2 == "age_binned") group = "AB"
    else if ($2 == "continuous_age") group = "AC"
    else if ($2 == "hz_notebook") group = "HZ"
    if (group != "") print $1 "\t" group
  }' "${GTEX_MODEL_LIST}" > "${model_tsv}"
  awk -F $'\t' 'NR > 1 { print $1 }' "${GTEX_BROAD_TISSUE_LIST}" > "${tissue_tsv}"

  {
    printf "task_id\ttissue_id\tmodel_group\tmodel_id\tcounts_gct\tsample_metadata_tsv\tsubject_metadata_tsv\thuman_gene_info\tgtf\n"
    awk -F $'\t' \
      -v model_tsv="${model_tsv}" \
      -v tissue_tsv="${tissue_tsv}" \
      -v filter_group="${FILTER_MODEL_GROUP}" \
      -v filter_tissue="${FILTER_TISSUE_ID}" \
      -v filter_models="${FILTER_MODEL_IDS}" \
      -v v10_counts="${GTEX_V10_COUNTS_GCT}" \
      -v v10_sample="${GTEX_V10_SAMPLE_ATTRIBUTES_TSV}" \
      -v v10_subject="${GTEX_V10_SUBJECT_PHENOTYPES_TSV}" \
      -v v8_counts="${GTEX_V8_COUNTS_GCT}" \
      -v v8_sample="${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}" \
      -v v8_subject="${GTEX_V8_SUBJECT_PHENOTYPES_TSV}" \
      -v v8_hgi="${GTEX_V8_HUMAN_GENE_INFO}" \
      -v gtf="${GTEX_GTF}" '
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
        split(filter_models, requested_models, ",")
        for (requested_index in requested_models) {
          requested_model = requested_models[requested_index]
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", requested_model)
          if (requested_model != "") {
            requested_model_lookup[requested_model] = 1
          }
        }
        task_id = 0
        for (ti = 1; ti <= n_tissues; ti++) {
          tissue_id = tissues[ti]
          if (filter_tissue != "" && tissue_id != filter_tissue) continue
          for (mi = 1; mi <= n_models; mi++) {
            model_id = model_ids[mi]
            model_group = model_groups[mi]
            if (filter_group != "" && model_group != filter_group) continue
            if (filter_models != "" && !(model_id in requested_model_lookup)) continue
            task_id += 1
            if (model_group == "HZ") {
              printf "%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", task_id, tissue_id, model_group, model_id, v8_counts, v8_sample, v8_subject, v8_hgi, gtf
            } else {
              printf "%d\t%s\t%s\t%s\t%s\t%s\t%s\t\t%s\n", task_id, tissue_id, model_group, model_id, v10_counts, v10_sample, v10_subject, gtf
            }
          }
        }
      }'
  } > "${GTEX_WORKLIST}"
  rm -f "${model_tsv}" "${tissue_tsv}"

  if [[ "$(awk 'END { print NR - 1 }' "${GTEX_WORKLIST}")" -le 0 ]]; then
    echo "GTEx filters produced an empty worklist" >&2
    exit 1
  fi
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]] || return 0
  local filtered_worklist kept
  filtered_worklist="$(mktemp)"
  head -n 1 "${GTEX_WORKLIST}" > "${filtered_worklist}"
  kept=0
  while IFS= read -r row; do
    [[ -n "${row}" ]] || continue
    local tissue_id model_id suffix model_dir
    IFS=$'\t' read -r _task_id tissue_id _model_group model_id _rest <<< "${row}"
    suffix="${row#*$'\t'}"
    model_dir="${GTEX_OUT_ROOT}/genesets/${tissue_id}/models/${model_id}"
    if [[ -d "${model_dir}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\n" "${kept}" "${suffix}" >> "${filtered_worklist}"
    fi
  done < <(tail -n +2 "${GTEX_WORKLIST}")
  mv "${filtered_worklist}" "${GTEX_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "GTEx refresh filters produced an empty worklist after excluding missing outputs" >&2
    exit 1
  fi
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
    append_bind_path "${DESCRIPTION_TEMPLATE_TSV:-}"
    append_bind_path "${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
    append_bind_path "${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
    append_bind_path "${GTEX_V10_COUNTS_GCT:-}"
    append_bind_path "${GTEX_V10_SAMPLE_ATTRIBUTES_TSV:-}"
    append_bind_path "${GTEX_V10_SUBJECT_PHENOTYPES_TSV:-}"
    append_bind_path "${GTEX_V8_COUNTS_GCT:-}"
    append_bind_path "${GTEX_V8_SAMPLE_ATTRIBUTES_TSV:-}"
    append_bind_path "${GTEX_V8_SUBJECT_PHENOTYPES_TSV:-}"
    append_bind_path "${GTEX_V8_HUMAN_GENE_INFO:-}"
    append_bind_path "${GTEX_GTF:-}"
  } | awk '!seen[$0]++' | paste -sd, -
}

submit_array() {
  prepare_common
  write_worklist
  filter_refresh_existing_worklist

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
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},GTEX_WORKLIST=${GTEX_WORKLIST},GTEX_OUT_ROOT=${GTEX_OUT_ROOT},GTEX_MODEL_LIST=${GTEX_MODEL_LIST},GTEX_BROAD_TISSUE_LIST=${GTEX_BROAD_TISSUE_LIST},GTEX_AGE_BINNED_MODEL_MANIFEST=${GTEX_AGE_BINNED_MODEL_MANIFEST},GTEX_CONTINUOUS_AGE_MODEL_MANIFEST=${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},RSCRIPT_BIN=${RSCRIPT_BIN},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV},GTEX_V10_COUNTS_GCT=${GTEX_V10_COUNTS_GCT},GTEX_V10_SAMPLE_ATTRIBUTES_TSV=${GTEX_V10_SAMPLE_ATTRIBUTES_TSV},GTEX_V10_SUBJECT_PHENOTYPES_TSV=${GTEX_V10_SUBJECT_PHENOTYPES_TSV},GTEX_V8_COUNTS_GCT=${GTEX_V8_COUNTS_GCT},GTEX_V8_SAMPLE_ATTRIBUTES_TSV=${GTEX_V8_SAMPLE_ATTRIBUTES_TSV},GTEX_V8_SUBJECT_PHENOTYPES_TSV=${GTEX_V8_SUBJECT_PHENOTYPES_TSV},GTEX_V8_HUMAN_GENE_INFO=${GTEX_V8_HUMAN_GENE_INFO},GTEX_GTF=${GTEX_GTF}" \
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
  APPTAINERENV_PYTHON_BIN="${APPTAINER_PYTHON_BIN}" \
  APPTAINERENV_RSCRIPT_BIN="${APPTAINER_RSCRIPT_BIN}" \
  APPTAINERENV_WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY}" \
  APPTAINERENV_REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE}" \
  APPTAINERENV_DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV}" \
  APPTAINERENV_PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX}" \
  APPTAINERENV_PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX}" \
  APPTAINERENV_LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV}" \
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

  local row tissue_id model_group model_id counts_gct sample_tsv subject_tsv human_gene_info gtf
  row="$(awk -F $'\t' -v target="${task_id}" 'NR > 1 && $1 == target { print; exit }' "${GTEX_WORKLIST}")"
  if [[ -z "${row}" ]]; then
    echo "No GTEx worklist row found for task ${task_id}" >&2
    exit 1
  fi

  IFS=$'\t' read -r _ tissue_id model_group model_id counts_gct sample_tsv subject_tsv human_gene_info gtf <<< "${row}"
  local tissue_label
  tissue_label="$(resolve_tissue_label "${tissue_id}")"
  if [[ -z "${tissue_label}" ]]; then
    echo "Missing tissue_name for GTEx tissue_id ${tissue_id}" >&2
    exit 1
  fi

  echo "GTEx task ${task_id}: tissue=${tissue_id} group=${model_group} model=${model_id}"

  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    local models_root runner
    models_root="${GTEX_OUT_ROOT}/genesets/${tissue_id}/models"
    case "${model_group}" in
      AB)
        runner="${REPO_ROOT}/geneset-extractor-dev/GTEx/src/run_age_binned_model.py"
        cmd=(
          "${PYTHON_BIN}" "${runner}"
          --model_id "${model_id}"
          --tissue_id "${tissue_id}"
          --tissue_label "${tissue_label}"
          --run_root "${models_root}"
          --python_bin "${PYTHON_BIN}"
          --dig_dir "${DIG_DIR}"
          --age_binned_model_manifest "${GTEX_AGE_BINNED_MODEL_MANIFEST}"
          --tissue_column "SMTS"
          --tissue_value "${tissue_label}"
          --write_model_only
        )
        ;;
      AC)
        runner="${REPO_ROOT}/geneset-extractor-dev/GTEx/src/run_continuous_age_model.py"
        cmd=(
          "${PYTHON_BIN}" "${runner}"
          --tissue_id "${tissue_id}"
          --tissue_label "${tissue_label}"
          --model_ids "${model_id}"
          --run_root "${models_root}"
          --python_bin "${PYTHON_BIN}"
          --rscript_bin "${RSCRIPT_BIN}"
          --dig_dir "${DIG_DIR}"
          --continuous_age_model_manifest "${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST}"
          --tissue_column "SMTS"
          --tissue_value "${tissue_label}"
          --write_model_only
        )
        ;;
      HZ)
        runner="${REPO_ROOT}/geneset-extractor-dev/GTEx/src/run_hz_notebook_model.py"
        cmd=(
          "${PYTHON_BIN}" "${runner}"
          --model_id "${model_id}"
          --tissue_id "${tissue_id}"
          --tissue_label "${tissue_label}"
          --run_root "${models_root}"
          --python_bin "${PYTHON_BIN}"
          --rscript_bin "${RSCRIPT_BIN}"
          --dig_dir "${DIG_DIR}"
          --tissue_column "SMTS"
          --tissue_value "${tissue_label}"
          --write_model_only
        )
        ;;
      *)
        echo "Unsupported GTEx model group in model-only mode: ${model_group}" >&2
        exit 1
        ;;
    esac
    echo "+ ${cmd[*]}"
    "${cmd[@]}"
    return
  fi

  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    local model_dir refresh_cmd
    model_dir="${GTEX_OUT_ROOT}/genesets/${tissue_id}/models/${model_id}"
    refresh_cmd=(
      bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
      --model_id "${model_id}"
      --model_dir "${model_dir}"
      --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}"
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
    bash "${REPO_ROOT}/geneset-extractor-dev/GTEx/run/build_genesets.sh"
    --tissue_granularity broad
    --tissues "${tissue_id}"
    --models "${model_id}"
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
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  GTEX_OUT_ROOT="$(absolute_path "${GTEX_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  GTEX_WORKLIST="$(absolute_path "${GTEX_WORKLIST}")"

  if [[ $# -eq 0 ]] && [[ -n "${PBS_ARRAYID:-}" || -n "${SGE_TASK_ID:-}" ]]; then
    run_task
    return
  fi

  parse_cli "$@"
  submit_array
}

main "$@"
