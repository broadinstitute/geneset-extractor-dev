#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
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
SUBMIT_MODE=0
WRITE_MODEL_ONLY=0
REFRESH_METADATA_AND_PROVENANCE=0
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-}"
FILTER_MODEL_GROUP=""
FILTER_TISSUE_ID=""
FILTER_MODEL_ID=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_gtex_models_cluster.sh --submit [--write_model_only|--refresh_metadata_and_provenance] [--model_group AB|AC|HZ] [--tissue_id TISSUE] [--model_id MODEL]
  ./geneset-extractor-dev/run/submit_gtex_models_cluster.sh --help

Required environment variables:

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, RSCRIPT_BIN, QSUB_BIN
  GTEX_OUT_ROOT, QSUB_LOG_ROOT, GTEX_WORKLIST
  GTEX_ARRAY_MEMORY, GTEX_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV

Notes:
  - Use --submit to submit the qsub array.
  - Add --write_model_only to write only geneset.model.json sidecars.
  - Add --refresh_metadata_and_provenance to patch metadata descriptions and
    rebuild provenance for each selected model output.
  - Full workflow runs require GTEX_V10_*, GTEX_V8_*, GTEX_V8_HUMAN_GENE_INFO,
    and GTEX_GTF. Model-only runs do not.
  - When run inside a qsub array task, it auto-detects the task context and
    runs the assigned workload row.
  - No filters: one array covering all tissue+model tasks.
  - --model_group: one array for all tissue+model tasks in that group.
  - --tissue_id: one array for all models for that tissue.
  - --model_id alone: one array for that model across all tissues.
  - --model_id plus --tissue_id: one single-task submission.
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

  if [[ ${WRITE_MODEL_ONLY} -eq 1 && ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    echo "Use only one of --write_model_only or --refresh_metadata_and_provenance" >&2
    exit 1
  fi

  if [[ -n "${FILTER_MODEL_ID}" ]]; then
    local derived_group
    derived_group="$(resolve_model_group_for_id "${FILTER_MODEL_ID}")"
    if [[ -z "${derived_group}" ]]; then
      echo "Model not found in GTEx model list: ${FILTER_MODEL_ID}" >&2
      exit 1
    fi
    if [[ -n "${FILTER_MODEL_GROUP}" && "${FILTER_MODEL_GROUP}" != "${derived_group}" ]]; then
      echo "--model_id ${FILTER_MODEL_ID} conflicts with --model_group ${FILTER_MODEL_GROUP}" >&2
      exit 1
    fi
    FILTER_MODEL_GROUP="${derived_group}"
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

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"

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
      -v filter_model="${FILTER_MODEL_ID}" \
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
        task_id = 0
        for (ti = 1; ti <= n_tissues; ti++) {
          tissue_id = tissues[ti]
          if (filter_tissue != "" && tissue_id != filter_tissue) continue
          for (mi = 1; mi <= n_models; mi++) {
            model_id = model_ids[mi]
            model_group = model_groups[mi]
            if (filter_group != "" && model_group != filter_group) continue
            if (filter_model != "" && model_id != filter_model) continue
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

submit_array() {
  prepare_common
  write_worklist

  local tasks job_name
  tasks="$(awk 'END { print NR - 1 }' "${GTEX_WORKLIST}")"
  job_name="${GTEX_JOB_NAME:-gtex_all_models}"

  echo "GTEx worklist: ${GTEX_WORKLIST} (${tasks} tasks)"

  "${QSUB_BIN}" \
    -N "${job_name}" \
    -t "1-${tasks}" \
    -o "${QSUB_LOG_ROOT}/gtex.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/gtex.\$TASK_ID.err" \
    -l "h_vmem=${GTEX_ARRAY_MEMORY},h_rt=${GTEX_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},GTEX_WORKLIST=${GTEX_WORKLIST},GTEX_OUT_ROOT=${GTEX_OUT_ROOT},GTEX_MODEL_LIST=${GTEX_MODEL_LIST},GTEX_BROAD_TISSUE_LIST=${GTEX_BROAD_TISSUE_LIST},GTEX_AGE_BINNED_MODEL_MANIFEST=${GTEX_AGE_BINNED_MODEL_MANIFEST},GTEX_CONTINUOUS_AGE_MODEL_MANIFEST=${GTEX_CONTINUOUS_AGE_MODEL_MANIFEST},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},RSCRIPT_BIN=${RSCRIPT_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},GTEX_V10_COUNTS_GCT=${GTEX_V10_COUNTS_GCT},GTEX_V10_SAMPLE_ATTRIBUTES_TSV=${GTEX_V10_SAMPLE_ATTRIBUTES_TSV},GTEX_V10_SUBJECT_PHENOTYPES_TSV=${GTEX_V10_SUBJECT_PHENOTYPES_TSV},GTEX_V8_COUNTS_GCT=${GTEX_V8_COUNTS_GCT},GTEX_V8_SAMPLE_ATTRIBUTES_TSV=${GTEX_V8_SAMPLE_ATTRIBUTES_TSV},GTEX_V8_SUBJECT_PHENOTYPES_TSV=${GTEX_V8_SUBJECT_PHENOTYPES_TSV},GTEX_V8_HUMAN_GENE_INFO=${GTEX_V8_HUMAN_GENE_INFO},GTEX_GTF=${GTEX_GTF}" \
    "${BASH_SOURCE[0]}"
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then
    echo "GTEx worker requires PBS_ARRAYID or SGE_TASK_ID" >&2
    exit 1
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
    local cmd models_root runner
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
