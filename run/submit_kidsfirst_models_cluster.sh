#!/usr/bin/env bash
set -euo pipefail

# Branch-standard cluster submit wrapper for the KidsFirst library.
# Mirrors submit_gtex_models_cluster.sh / submit_motrpac_models_cluster.sh:
# config-driven, environment-driven, working-directory independent, no in-script
# path editing required. KidsFirst has a single published model family (HZ1,
# harmonizome-style DE); the natural partition is the comparison_id.
#
# Fully implemented operations (work against existing model outputs):
#   --write_model_only               regenerate geneset.model.json sidecars
#   --refresh_metadata_and_provenance  refresh metadata/provenance/GMT descriptions,
#                                      inject public source identifiers, write .orig
#
# The differential-expression build itself (matrix prep -> rna_de_prepare ->
# rna_deg_multi) is produced by the DIG workflow driven from run/sbatch_01..03.sh;
# a bare --submit (full rebuild) delegates there (see --help).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_kidsfirst_models_cluster.sh"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

KIDSFIRST_CONFIG_ROOT="${KIDSFIRST_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/KidsFirst/config}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

KIDSFIRST_MODEL_LIST="${KIDSFIRST_MODEL_LIST:-${KIDSFIRST_CONFIG_ROOT}/model_list.tsv}"
KIDSFIRST_COMPARISON_LIST="${KIDSFIRST_COMPARISON_LIST:-${KIDSFIRST_CONFIG_ROOT}/comparison_list.tsv}"
KIDSFIRST_MODEL_MANIFEST="${KIDSFIRST_MODEL_MANIFEST:-${KIDSFIRST_CONFIG_ROOT}/model_manifest.tsv}"
DESCRIPTION_TEMPLATE_TSV="${DESCRIPTION_TEMPLATE_TSV:-${KIDSFIRST_CONFIG_ROOT}/model_description_templates.tsv}"

KIDSFIRST_OUT_ROOT="${KIDSFIRST_OUT_ROOT:-${WORK_ROOT}/kidsfirst_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_kidsfirst}"
KIDSFIRST_WORKLIST="${KIDSFIRST_WORKLIST:-${WORK_ROOT}/kidsfirst_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"

KIDSFIRST_ARRAY_MEMORY="${KIDSFIRST_ARRAY_MEMORY:-16G}"
KIDSFIRST_ARRAY_WALLTIME="${KIDSFIRST_ARRAY_WALLTIME:-08:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
LOCAL_INPUT_SOURCE_MAP_TSV="${LOCAL_INPUT_SOURCE_MAP_TSV:-}"
FILTER_MODEL_IDS=""
FILTER_COMPARISON_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_kidsfirst_models_cluster.sh --submit (--write_model_only|--refresh_metadata_and_provenance) [--model_id MODEL[,MODEL...]] [--comparison COMP[,COMP...]]
  ./geneset-extractor-dev/run/submit_kidsfirst_models_cluster.sh --help

Optional environment variables:
  WORK_ROOT, REPO_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  KIDSFIRST_CONFIG_ROOT, KIDSFIRST_MODEL_LIST, KIDSFIRST_COMPARISON_LIST, KIDSFIRST_MODEL_MANIFEST
  KIDSFIRST_OUT_ROOT, QSUB_LOG_ROOT, KIDSFIRST_WORKLIST
  KIDSFIRST_ARRAY_MEMORY, KIDSFIRST_ARRAY_WALLTIME
  DESCRIPTION_TEMPLATE_TSV
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX
  LOCAL_INPUT_SOURCE_MAP_TSV

Notes:
  - Worklist = every enabled model in model_list.tsv paired with every
    comparison in comparison_list.tsv whose model_eligible column lists it.
  - --write_model_only: (re)write geneset.model.json for each selected model output.
  - --refresh_metadata_and_provenance: refresh metadata descriptions, provenance,
    and GMT second-column descriptions; inject public source identifiers from
    LOCAL_INPUT_SOURCE_MAP_TSV; preserve originals as .orig. Set
    PROVENANCE_MIRROR_LOCAL_PREFIX/PROVENANCE_MIRROR_REMOTE_PREFIX to rewrite the
    local output root to a publish-safe location.
  - Full DE rebuild: run the two-phase pipeline first (run/sbatch_01_de_only.sh,
    run/sbatch_02_cbtn_de.sh, run/sbatch_03_extract_genesets.sh) to populate
    ${KIDSFIRST_OUT_ROOT}; then use --write_model_only and
    --refresh_metadata_and_provenance here. A bare --submit without a sub-mode
    is rejected so the pipeline stage is explicit.
EOF
}

require_file() { [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }; }
require_dir()  { [[ -d "$1" ]] || { echo "Missing required directory: $1" >&2; exit 1; }; }

absolute_path() {
  local path="$1"
  if [[ "${path}" == /* ]]; then printf '%s\n' "${path}"; else printf '%s/%s\n' "$(pwd)" "${path}"; fi
}

parse_cli() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --submit) SUBMIT_MODE=1; shift ;;
      --write_model_only) WRITE_MODEL_ONLY=1; shift ;;
      --refresh_metadata_and_provenance) REFRESH_METADATA_AND_PROVENANCE=1; shift ;;
      --model_id) [[ $# -ge 2 ]] || { echo "Missing value for --model_id" >&2; exit 1; }; FILTER_MODEL_IDS="$2"; shift 2 ;;
      --comparison) [[ $# -ge 2 ]] || { echo "Missing value for --comparison" >&2; exit 1; }; FILTER_COMPARISON_IDS="$2"; shift 2 ;;
      -h|--help|help) usage; exit 0 ;;
      *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done
  if [[ ${WRITE_MODEL_ONLY} -eq 1 && ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    echo "Use only one of --write_model_only or --refresh_metadata_and_provenance" >&2; exit 1
  fi
  if [[ ${SUBMIT_MODE} -ne 1 ]]; then usage; exit 1; fi
  if [[ ${WRITE_MODEL_ONLY} -ne 1 && ${REFRESH_METADATA_AND_PROVENANCE} -ne 1 ]]; then
    echo "A sub-mode is required: --write_model_only or --refresh_metadata_and_provenance." >&2
    echo "For a full DE rebuild run run/sbatch_01..03.sh first (see --help)." >&2
    exit 1
  fi
}

write_worklist() {
  awk -F $'\t' \
    -v model_list="${KIDSFIRST_MODEL_LIST}" \
    -v filter_models="${FILTER_MODEL_IDS}" \
    -v filter_comps="${FILTER_COMPARISON_IDS}" '
    BEGIN {
      while ((getline line < model_list) > 0) {
        n = split(line, f, "\t")
        if (++ml_row == 1) { for (i=1;i<=n;i++){ if(f[i]=="model_id")mi=i; if(f[i]=="enabled")ei=i } ; continue }
        if (f[ei] == "true") enabled[f[mi]] = 1
      }
      close(model_list)
      split(filter_models, fm, ","); for (i in fm){ gsub(/[[:space:]]/,"",fm[i]); if(fm[i]!="") want_model[fm[i]]=1 }
      split(filter_comps, fc, ","); for (i in fc){ gsub(/[[:space:]]/,"",fc[i]); if(fc[i]!="") want_comp[fc[i]]=1 }
      print "task_id\tcomparison_id\tmodel_id"
    }
    NR==1 { for (i=1;i<=NF;i++){ if($i=="comparison_id")ci=i; if($i=="model_eligible")eli=i } ; next }
    {
      comp=$ci
      if (length(want_comp) && !(comp in want_comp)) next
      n=split($eli, elig, ",")
      for (k=1;k<=n;k++){
        m=elig[k]; gsub(/[[:space:]]/,"",m)
        if (!(m in enabled)) continue
        if (length(want_model) && !(m in want_model)) continue
        printf "%d\t%s\t%s\n", ++task, comp, m
      }
    }
  ' "${KIDSFIRST_COMPARISON_LIST}" > "${KIDSFIRST_WORKLIST}"

  if [[ "$(awk 'END { print NR - 1 }' "${KIDSFIRST_WORKLIST}")" -le 0 ]]; then
    echo "KidsFirst filters produced an empty worklist" >&2; exit 1
  fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"
  require_file "${KIDSFIRST_MODEL_LIST}"
  require_file "${KIDSFIRST_COMPARISON_LIST}"
  require_file "${KIDSFIRST_MODEL_MANIFEST}"
  require_file "${DESCRIPTION_TEMPLATE_TSV}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 && -n "${LOCAL_INPUT_SOURCE_MAP_TSV}" ]]; then
    require_file "${LOCAL_INPUT_SOURCE_MAP_TSV}"
  fi
}

run_task() {
  local task_id="${PBS_ARRAYID:-${SGE_TASK_ID:-}}"
  if [[ -z "${task_id}" ]]; then echo "KidsFirst worker requires PBS_ARRAYID or SGE_TASK_ID" >&2; exit 1; fi
  local row comparison_id model_id
  row="$(awk -F $'\t' -v t="${task_id}" 'NR>1 && $1==t { print; exit }' "${KIDSFIRST_WORKLIST}")"
  if [[ -z "${row}" ]]; then echo "No KidsFirst worklist row for task ${task_id}" >&2; exit 1; fi
  IFS=$'\t' read -r _ comparison_id model_id <<< "${row}"
  local models_root model_dir
  models_root="${KIDSFIRST_OUT_ROOT}/genesets/${comparison_id}/models"
  model_dir="${models_root}/${model_id}"
  echo "KidsFirst task ${task_id}: comparison=${comparison_id} model=${model_id}"

  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    local cmd=(
      "${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/KidsFirst/src/run_kidsfirst_hz_model.py"
      --model_id "${model_id}" --comparison_id "${comparison_id}"
      --run_root "${models_root}" --config_dir "${KIDSFIRST_CONFIG_ROOT}"
      --python_bin "${PYTHON_BIN}" --dig_dir "${DIG_DIR}" --write_model_only
    )
    echo "+ ${cmd[*]}"; "${cmd[@]}"; return
  fi

  local refresh_cmd=(
    bash "${REPO_ROOT}/geneset-extractor-dev/run/refresh_model_metadata_and_provenance.sh"
    --model_id "${model_id}" --model_dir "${model_dir}"
    --description_template_tsv "${DESCRIPTION_TEMPLATE_TSV}" --python_bin "${PYTHON_BIN}"
  )
  [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX}"  ]] && refresh_cmd+=(--provenance_mirror_local_prefix  "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
  [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX}" ]] && refresh_cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
  [[ -n "${LOCAL_INPUT_SOURCE_MAP_TSV}"      ]] && refresh_cmd+=(--local_input_source_map_tsv      "${LOCAL_INPUT_SOURCE_MAP_TSV}")
  echo "+ ${refresh_cmd[*]}"; DIG_DIR="${DIG_DIR}" "${refresh_cmd[@]}"
}

submit_array() {
  prepare_common
  write_worklist
  local tasks job_name
  tasks="$(awk 'END { print NR - 1 }' "${KIDSFIRST_WORKLIST}")"
  job_name="${KIDSFIRST_JOB_NAME:-kidsfirst_all_models}"
  echo "KidsFirst worklist: ${KIDSFIRST_WORKLIST} (${tasks} tasks)"
  "${QSUB_BIN}" \
    -N "${job_name}" \
    -t "1-${tasks}" \
    -o "${QSUB_LOG_ROOT}/kidsfirst.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/kidsfirst.\$TASK_ID.err" \
    -l "h_vmem=${KIDSFIRST_ARRAY_MEMORY},h_rt=${KIDSFIRST_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},KIDSFIRST_WORKLIST=${KIDSFIRST_WORKLIST},KIDSFIRST_OUT_ROOT=${KIDSFIRST_OUT_ROOT},KIDSFIRST_CONFIG_ROOT=${KIDSFIRST_CONFIG_ROOT},KIDSFIRST_MODEL_LIST=${KIDSFIRST_MODEL_LIST},KIDSFIRST_COMPARISON_LIST=${KIDSFIRST_COMPARISON_LIST},KIDSFIRST_MODEL_MANIFEST=${KIDSFIRST_MODEL_MANIFEST},DESCRIPTION_TEMPLATE_TSV=${DESCRIPTION_TEMPLATE_TSV},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX},LOCAL_INPUT_SOURCE_MAP_TSV=${LOCAL_INPUT_SOURCE_MAP_TSV}" \
    "${SELF_PATH}"
}

main() {
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  KIDSFIRST_OUT_ROOT="$(absolute_path "${KIDSFIRST_OUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  KIDSFIRST_WORKLIST="$(absolute_path "${KIDSFIRST_WORKLIST}")"
  if [[ $# -eq 0 ]] && [[ -n "${PBS_ARRAYID:-}" || -n "${SGE_TASK_ID:-}" ]]; then
    run_task
    return
  fi
  parse_cli "$@"
  submit_array
}

main "$@"
