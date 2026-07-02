#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_ROOT="${WORK_ROOT:-$(pwd)}"

GEO_BULK_CONFIG_ROOT="${GEO_BULK_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/GEO_BULK/config}"
GEO_BULK_SRC_ROOT="${GEO_BULK_SRC_ROOT:-${REPO_ROOT}/geneset-extractor-dev/GEO_BULK/src}"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"

GEO_BULK_DATASET_LIST="${GEO_BULK_DATASET_LIST:-${GEO_BULK_CONFIG_ROOT}/dataset_list.tsv}"
GEO_BULK_MODEL_MANIFEST="${GEO_BULK_MODEL_MANIFEST:-${GEO_BULK_CONFIG_ROOT}/model_manifest.tsv}"
GEO_BULK_DESCRIPTION_TEMPLATES="${GEO_BULK_DESCRIPTION_TEMPLATES:-${GEO_BULK_CONFIG_ROOT}/model_description_templates.tsv}"

GEO_BULK_INPUT_ROOT="${GEO_BULK_INPUT_ROOT:-${WORK_ROOT}/inputs/GEO_BULK}"
GEO_BULK_OUT_ROOT="${GEO_BULK_OUT_ROOT:-${WORK_ROOT}/geo_bulk_all_models}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_geo_bulk}"
GEO_BULK_WORKLIST="${GEO_BULK_WORKLIST:-${WORK_ROOT}/geo_bulk_qsub_worklist.tsv}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
QSUB_BIN="${QSUB_BIN:-qsub}"

GEO_BULK_ARRAY_MEMORY="${GEO_BULK_ARRAY_MEMORY:-16G}"
GEO_BULK_ARRAY_WALLTIME="${GEO_BULK_ARRAY_WALLTIME:-24:00:00}"
SUBMIT_MODE="${SUBMIT_MODE:-0}"
WRITE_MODEL_ONLY="${WRITE_MODEL_ONLY:-0}"
REFRESH_METADATA_AND_PROVENANCE="${REFRESH_METADATA_AND_PROVENANCE:-0}"
BACKEND="${GEO_BULK_BACKEND:-}"
PROVENANCE_MIRROR_LOCAL_PREFIX="${PROVENANCE_MIRROR_LOCAL_PREFIX:-}"
PROVENANCE_MIRROR_REMOTE_PREFIX="${PROVENANCE_MIRROR_REMOTE_PREFIX:-}"
FILTER_MODEL_IDS=""
FILTER_DATASET_IDS=""

usage() {
  cat <<'EOF'
Usage:
  ./geneset-extractor-dev/run/submit_geo_bulk_models_cluster.sh --submit \
      [--write_model_only|--refresh_metadata_and_provenance] \
      [--model_id GB1[,GB2...]] [--dataset_id GSE1[,GSE2...]]
  ./geneset-extractor-dev/run/submit_geo_bulk_models_cluster.sh --help

Optional environment variables:
  WORK_ROOT
  DIG_DIR, PYTHON_BIN, QSUB_BIN
  GEO_BULK_INPUT_ROOT, GEO_BULK_OUT_ROOT, QSUB_LOG_ROOT, GEO_BULK_WORKLIST
  GEO_BULK_DATASET_LIST, GEO_BULK_MODEL_MANIFEST, GEO_BULK_DESCRIPTION_TEMPLATES
  GEO_BULK_ARRAY_MEMORY, GEO_BULK_ARRAY_WALLTIME, GEO_BULK_BACKEND
  PROVENANCE_MIRROR_LOCAL_PREFIX, PROVENANCE_MIRROR_REMOTE_PREFIX

Notes:
  - GEO_BULK partitions by GEO dataset id; each enabled (dataset_id, model_id)
    pair is one array task running the DIG-owned geo_bulk_prepare + rna_de_prepare
    workflows via GEO_BULK/src/run_geo_bulk_model.py.
  - Use --submit to submit the qsub array.
  - --write_model_only regenerates geneset.model.json sidecars from config for
    existing outputs.
  - --refresh_metadata_and_provenance re-runs sidecar regeneration, metadata /
    provenance / GMT-description refresh, path sanitization, and canonical
    artifact promotion for existing outputs without recomputing differential
    expression.
  - No filters: one array covering all enabled datasets x enabled models.
EOF
}

require_file() { [[ -f "$1" ]] || { echo "Missing required file: $1" >&2; exit 1; }; }
require_dir() { [[ -d "$1" ]] || { echo "Missing required directory: $1" >&2; exit 1; }; }

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
      --dataset_id) [[ $# -ge 2 ]] || { echo "Missing value for --dataset_id" >&2; exit 1; }; FILTER_DATASET_IDS="$2"; shift 2 ;;
      -h|--help|help) usage; exit 0 ;;
      *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done
  if [[ ${WRITE_MODEL_ONLY} -eq 1 && ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    echo "Use only one of --write_model_only or --refresh_metadata_and_provenance" >&2
    exit 1
  fi
  if [[ ${SUBMIT_MODE} -ne 1 ]]; then usage; exit 1; fi
}

prepare_common() {
  mkdir -p "${WORK_ROOT}" "${QSUB_LOG_ROOT}"
  require_dir "${DIG_DIR}"
  require_file "${GEO_BULK_DATASET_LIST}"
  require_file "${GEO_BULK_MODEL_MANIFEST}"
  if [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 || ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    require_file "${GEO_BULK_DESCRIPTION_TEMPLATES}"
  fi
}

write_worklist() {
  {
    printf "task_id\tdataset_id\tmodel_id\n"
    "${PYTHON_BIN}" - "$@" <<'PY'
import csv, sys
dataset_list, model_manifest, filter_models, filter_datasets = sys.argv[1:5]

def enabled_rows(path, key):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    out = []
    for row in rows:
        ident = str(row.get(key, "")).strip()
        if not ident:
            continue
        enabled = str(row.get("enabled", "true")).strip().lower()
        if "enabled" in row and enabled not in {"1", "true", "yes"}:
            continue
        out.append(ident)
    return out

datasets = enabled_rows(dataset_list, "dataset_id")
models = enabled_rows(model_manifest, "model_id")
want_models = {m.strip() for m in filter_models.split(",") if m.strip()}
want_datasets = {d.strip() for d in filter_datasets.split(",") if d.strip()}
if want_models:
    models = [m for m in models if m in want_models]
if want_datasets:
    datasets = [d for d in datasets if d in want_datasets]
task_id = 0
for dataset in datasets:
    for model in models:
        task_id += 1
        print(f"{task_id}\t{dataset}\t{model}")
PY
  } > "${GEO_BULK_WORKLIST}"
}

filter_refresh_existing_worklist() {
  [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 || ${WRITE_MODEL_ONLY} -eq 1 ]] || return 0
  local filtered kept
  filtered="$(mktemp)"
  head -n 1 "${GEO_BULK_WORKLIST}" > "${filtered}"
  kept=0
  while IFS=$'\t' read -r _task_id dataset_id model_id; do
    [[ -n "${dataset_id:-}" ]] || continue
    if [[ -d "${GEO_BULK_OUT_ROOT}/genesets/${dataset_id}/models/${model_id}/extractor" ]]; then
      kept=$((kept + 1))
      printf "%d\t%s\t%s\n" "${kept}" "${dataset_id}" "${model_id}" >> "${filtered}"
    fi
  done < <(tail -n +2 "${GEO_BULK_WORKLIST}")
  mv "${filtered}" "${GEO_BULK_WORKLIST}"
  if [[ ${kept} -le 0 ]]; then
    echo "No GEO_BULK refresh tasks selected after excluding missing outputs." >&2
    exit 1
  fi
}

worklist_task_count() { awk 'NR > 1 { n += 1 } END { print n + 0 }' "${GEO_BULK_WORKLIST}"; }

task_id_from_env() {
  if [[ -n "${PBS_ARRAYID:-}" ]]; then printf '%s\n' "${PBS_ARRAYID}"; return; fi
  if [[ -n "${SGE_TASK_ID:-}" ]]; then printf '%s\n' "${SGE_TASK_ID}"; return; fi
  return 1
}

run_worker() {
  local task_id dataset_id model_id
  task_id="$(task_id_from_env)" || { echo "Unable to determine array task id" >&2; exit 1; }
  IFS=$'\t' read -r _task_id dataset_id model_id < <(awk -F $'\t' -v t="${task_id}" 'NR > 1 && $1 == t { print; exit }' "${GEO_BULK_WORKLIST}")
  if [[ -z "${dataset_id:-}" ]]; then
    echo "No GEO_BULK worklist row found for task_id=${task_id}" >&2
    exit 1
  fi
  local cmd
  cmd=(
    "${PYTHON_BIN}"
    "${GEO_BULK_SRC_ROOT}/run_geo_bulk_model.py"
    "--dataset_id" "${dataset_id}"
    "--model_id" "${model_id}"
    "--dataset_list" "${GEO_BULK_DATASET_LIST}"
    "--model_manifest" "${GEO_BULK_MODEL_MANIFEST}"
    "--description_templates" "${GEO_BULK_DESCRIPTION_TEMPLATES}"
    "--dig_dir" "${DIG_DIR}"
    "--input_root" "${GEO_BULK_INPUT_ROOT}"
    "--out_root" "${GEO_BULK_OUT_ROOT}"
    "--python_bin" "${PYTHON_BIN}"
  )
  [[ -n "${BACKEND}" ]] && cmd+=(--backend "${BACKEND}")
  [[ -n "${PROVENANCE_MIRROR_LOCAL_PREFIX}" ]] && cmd+=(--provenance_mirror_local_prefix "${PROVENANCE_MIRROR_LOCAL_PREFIX}")
  [[ -n "${PROVENANCE_MIRROR_REMOTE_PREFIX}" ]] && cmd+=(--provenance_mirror_remote_prefix "${PROVENANCE_MIRROR_REMOTE_PREFIX}")
  if [[ ${WRITE_MODEL_ONLY} -eq 1 ]]; then
    cmd+=(--write_model_only)
  elif [[ ${REFRESH_METADATA_AND_PROVENANCE} -eq 1 ]]; then
    cmd+=(--refresh_metadata_and_provenance)
  else
    cmd+=(--overwrite)
  fi
  printf '$'; printf ' %q' "${cmd[@]}"; printf '\n'
  "${cmd[@]}"
}

submit_array() {
  write_worklist "${GEO_BULK_DATASET_LIST}" "${GEO_BULK_MODEL_MANIFEST}" "${FILTER_MODEL_IDS}" "${FILTER_DATASET_IDS}"
  filter_refresh_existing_worklist
  local task_count
  task_count="$(worklist_task_count)"
  if [[ "${task_count}" -le 0 ]]; then echo "No GEO_BULK tasks selected." >&2; exit 1; fi
  "${QSUB_BIN}" \
    -N "geo_bulk_all_models" \
    -t "1-${task_count}" \
    -o "${QSUB_LOG_ROOT}/geo_bulk.\$TASK_ID.out" \
    -e "${QSUB_LOG_ROOT}/geo_bulk.\$TASK_ID.err" \
    -l "h_vmem=${GEO_BULK_ARRAY_MEMORY},h_rt=${GEO_BULK_ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},WORK_ROOT=${WORK_ROOT},GEO_BULK_WORKLIST=${GEO_BULK_WORKLIST},GEO_BULK_OUT_ROOT=${GEO_BULK_OUT_ROOT},GEO_BULK_INPUT_ROOT=${GEO_BULK_INPUT_ROOT},GEO_BULK_DATASET_LIST=${GEO_BULK_DATASET_LIST},GEO_BULK_MODEL_MANIFEST=${GEO_BULK_MODEL_MANIFEST},GEO_BULK_DESCRIPTION_TEMPLATES=${GEO_BULK_DESCRIPTION_TEMPLATES},GEO_BULK_SRC_ROOT=${GEO_BULK_SRC_ROOT},DIG_DIR=${DIG_DIR},PYTHON_BIN=${PYTHON_BIN},WRITE_MODEL_ONLY=${WRITE_MODEL_ONLY},REFRESH_METADATA_AND_PROVENANCE=${REFRESH_METADATA_AND_PROVENANCE},GEO_BULK_BACKEND=${BACKEND},PROVENANCE_MIRROR_LOCAL_PREFIX=${PROVENANCE_MIRROR_LOCAL_PREFIX},PROVENANCE_MIRROR_REMOTE_PREFIX=${PROVENANCE_MIRROR_REMOTE_PREFIX}" \
    "${REPO_ROOT}/geneset-extractor-dev/run/submit_geo_bulk_models_cluster.sh"
}

main() {
  WORK_ROOT="$(absolute_path "${WORK_ROOT}")"
  GEO_BULK_OUT_ROOT="$(absolute_path "${GEO_BULK_OUT_ROOT}")"
  GEO_BULK_INPUT_ROOT="$(absolute_path "${GEO_BULK_INPUT_ROOT}")"
  QSUB_LOG_ROOT="$(absolute_path "${QSUB_LOG_ROOT}")"
  GEO_BULK_WORKLIST="$(absolute_path "${GEO_BULK_WORKLIST}")"

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
