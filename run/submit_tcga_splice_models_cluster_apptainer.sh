#!/usr/bin/env bash
set -euo pipefail
# Submit TCGA SpliceSeq tumor-vs-normal models as a qsub array (Apptainer).
# One family (SP*); only projects with matched normals. Two-step: splice_prepare_public -> splice_event_matrix.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_ROOT="${REPO_ROOT:-${DEFAULT_REPO_ROOT}}"
SELF_PATH="${REPO_ROOT}/geneset-extractor-dev/run/submit_tcga_splice_models_cluster_apptainer.sh"
DIG_DIR="${DIG_DIR:-${REPO_ROOT}/dig-gene-set-extractors}"
WORK_ROOT="${WORK_ROOT:-${PWD}}"; PYTHON_BIN="${PYTHON_BIN:-python3}"
CONFIG_ROOT="${TCGA_SPLICE_CONFIG_ROOT:-${REPO_ROOT}/geneset-extractor-dev/NCI_GDC_TCGA_Splice/config}"
MODEL_LIST="${TCGA_SPLICE_MODEL_LIST:-${CONFIG_ROOT}/model_list.tsv}"
TUMOR_TYPE_LIST="${TCGA_SPLICE_TUMOR_TYPE_LIST:-${CONFIG_ROOT}/tumor_type_list.tsv}"
MODEL_MANIFEST="${TCGA_SPLICE_MODEL_MANIFEST:-${CONFIG_ROOT}/model_manifest.tsv}"
OUT_ROOT="${TCGA_SPLICE_OUT_ROOT:-${WORK_ROOT}/tcga_splice_all_models}"
WORKLIST="${TCGA_SPLICE_WORKLIST:-${WORK_ROOT}/tcga_splice_qsub_worklist.tsv}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${WORK_ROOT}/qsub_logs_tcga_splice}"
ARRAY_MEMORY="${TCGA_SPLICE_ARRAY_MEMORY:-16G}"; ARRAY_WALLTIME="${TCGA_SPLICE_ARRAY_WALLTIME:-12:00:00}"
JOB_NAME="${TCGA_SPLICE_JOB_NAME:-tcga_splice_models_apptainer}"; QSUB_BIN="${QSUB_BIN:-qsub}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"; APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"; APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
PSI_DIR="${TCGA_SPLICE_PSI_DIR:-}"
MODE="build"; FILTER_TUMOR_TYPE=""; FILTER_MODELS=""; OVERWRITE=""
usage(){ echo "Usage: $0 --submit [--write_model_only] [--tumor_type_id ID] [--model_id M[,M]] [--overwrite]"; }
require_file(){ [[ -f "$1" ]] || { echo "Missing file: $1" >&2; exit 1; }; }
require_var(){ [[ -n "${!1:-}" ]] || { echo "Missing env var: $1" >&2; exit 1; }; }
append_bind_path(){ [[ -z "${1:-}" ]] && return 0; [[ -d "$1" ]] && printf '%s\n' "$1" || dirname "$1"; }
write_worklist(){
  awk -F '\t' -v filter_tt="${FILTER_TUMOR_TYPE}" -v filter_models="${FILTER_MODELS}" -v model_list="${MODEL_LIST}" '
    BEGIN { n=0
      while ((getline line < model_list) > 0) { if (++ml==1) continue; split(line,f,"\t"); if (tolower(f[3])!="true") continue; models[++n]=f[1] }
      if (length(filter_models)>0){ split(filter_models,w,","); for(i in w) want[w[i]]=1; nw=1 } task=0 }
    NR==1 { next }
    { tt=$1; proj=$2; label=$3; hn=tolower($4)
      if (length(filter_tt)>0 && tt!=filter_tt) next
      if (hn!="true") next
      for (mi=1; mi<=n; mi++){ m=models[mi]; if (nw && !(m in want)) continue; printf "%d\t%s\t%s\t%s\t%s\n", ++task, tt, proj, label, m } }
  ' "${TUMOR_TYPE_LIST}" > "${WORKLIST}"
  [[ "$(awk 'END{print NR}' "${WORKLIST}")" -gt 0 ]] || { echo "Empty worklist" >&2; exit 1; }
}
run_task(){
  local task_id="${SGE_TASK_ID:-${SLURM_ARRAY_TASK_ID:-${1:-1}}}"
  local row tt proj label model
  row="$(awk -F '\t' -v t="${task_id}" '$1==t{print; exit}' "${WORKLIST}")"
  [[ -n "${row}" ]] || { echo "No worklist row for ${task_id}" >&2; exit 1; }
  IFS=$'\t' read -r _ tt proj label model <<<"${row}"
  mkdir -p "${OUT_ROOT}"
  local psi_tsv="${PSI_DIR}/${proj}.psi.tsv"
  local bind_csv inner
  bind_csv="$( { printf '%s\n' "${REPO_ROOT}" "${DIG_DIR}" "${OUT_ROOT}"; append_bind_path "${CONFIG_ROOT}"; append_bind_path "${PSI_DIR}"; } | awk 'NF && !seen[$0]++' | paste -sd, - )"
  if [[ "${MODE}" == "write_model_only" ]]; then
    inner="'${APPTAINER_PYTHON_BIN}' '${REPO_ROOT}/geneset-extractor-dev/NCI_GDC_TCGA_Splice/src/run_splice_tumor_vs_normal_model.py' --model_id '${model}' --tumor_type_id '${tt}' --tumor_type_label '${label}' --project_id '${proj}' --run_root '${OUT_ROOT}/genesets/${tt}/models' --dig_dir '${DIG_DIR}' --model_manifest '${MODEL_MANIFEST}' --write_model_only"
  else
    inner="'${APPTAINER_PYTHON_BIN}' '${REPO_ROOT}/geneset-extractor-dev/NCI_GDC_TCGA_Splice/src/build_tcga_splice_genesets.py' --tumor_types '${tt}' --models '${model}' --psi_dir '${PSI_DIR}' --dig_dir '${DIG_DIR}' --out_root '${OUT_ROOT}' --model_manifest '${MODEL_MANIFEST}' --model_list '${MODEL_LIST}' --tumor_type_list '${TUMOR_TYPE_LIST}'"
    [[ -n "${OVERWRITE}" ]] && inner+=" --overwrite"
  fi
  declare -a EXEC_CMD; EXEC_CMD=("${APPTAINER_BIN}" exec --bind "${bind_csv}")
  if [[ -n "${APPTAINER_EXTRA_ARGS}" ]]; then
    # shellcheck disable=SC2206
    EXTRA_ARGS=( ${APPTAINER_EXTRA_ARGS} ); EXEC_CMD+=("${EXTRA_ARGS[@]}"); fi
  EXEC_CMD+=("${APPTAINER_IMAGE}" bash --noprofile --norc -c "export PYTHONPATH='${DIG_DIR}/src'; ${inner}")
  echo "[task ${task_id}] ${tt} / ${model}"; exec "${EXEC_CMD[@]}"
}
do_submit(){
  require_var APPTAINER_IMAGE; require_file "${APPTAINER_IMAGE}"
  require_file "${MODEL_LIST}"; require_file "${TUMOR_TYPE_LIST}"; require_file "${MODEL_MANIFEST}"
  [[ "${MODE}" == "build" ]] && { require_var TCGA_SPLICE_PSI_DIR; [[ -d "${PSI_DIR}" ]] || { echo "Missing PSI_DIR: ${PSI_DIR}" >&2; exit 1; }; }
  write_worklist
  local tasks; tasks="$(awk 'END{print NR}' "${WORKLIST}")"; mkdir -p "${QSUB_LOG_ROOT}"
  echo "TCGA splice worklist: ${WORKLIST} (${tasks} tasks), mode=${MODE}"
  "${QSUB_BIN}" -t "1-${tasks}" -N "${JOB_NAME}" -o "${QSUB_LOG_ROOT}" -e "${QSUB_LOG_ROOT}" -j y \
    -l "h_vmem=${ARRAY_MEMORY},h_rt=${ARRAY_WALLTIME}" \
    -v "REPO_ROOT=${REPO_ROOT},DIG_DIR=${DIG_DIR},WORK_ROOT=${WORK_ROOT},PYTHON_BIN=${PYTHON_BIN},APPTAINER_IMAGE=${APPTAINER_IMAGE:-},TCGA_SPLICE_OUT_ROOT=${OUT_ROOT},TCGA_SPLICE_WORKLIST=${WORKLIST},TCGA_SPLICE_PSI_DIR=${PSI_DIR},TCGA_TASK_MODE=${MODE},TCGA_TASK_OVERWRITE=${OVERWRITE}" \
    "${SELF_PATH}" --run_task
}
[[ $# -ge 1 ]] || { usage >&2; exit 1; }
ACTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help|help) usage; exit 0 ;; --submit) ACTION="submit"; shift ;; --run_task) ACTION="run_task"; shift ;;
    --write_model_only) MODE="write_model_only"; shift ;; --overwrite) OVERWRITE="1"; shift ;;
    --tumor_type_id) FILTER_TUMOR_TYPE="$2"; shift 2 ;; --model_id) FILTER_MODELS="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done
MODE="${TCGA_TASK_MODE:-${MODE}}"; OVERWRITE="${TCGA_TASK_OVERWRITE:-${OVERWRITE}}"
case "${ACTION}" in submit) do_submit ;; run_task) run_task ;; *) echo "Specify --submit" >&2; usage >&2; exit 1 ;; esac
