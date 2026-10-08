#!/usr/bin/env bash
# Submit one existing provenance sidecar per Apptainer-backed array task.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_DIG_REPO="$(cd "${WRAPPER_DIR}/.." && pwd)/dig-gene-set-extractors"
DIG_DIR="${DIG_DIR:-${DIG_REPO:-${DEFAULT_DIG_REPO}}}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"
APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN:-python}"
QSUB_BIN="${QSUB_BIN:-qsub}"
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-}"
WORKLIST="${PROVENANCE_WORKLIST:-}"
TASK_INDEX="${SGE_TASK_ID:-${PBS_ARRAYID:-}}"
SUBMIT=0
OVERWRITE=0
INPUT=""

usage() {
  cat <<'EOF'
Usage: submit_convert_provenance_apptainer.sh <output-directory> [--overwrite] [--submit]

Without --submit, discovers files using DIG and writes a worklist. With
--submit, qsub runs one provenance conversion per array task.

Environment: APPTAINER_IMAGE and DIG_REPO (or DIG_DIR) are required for
--submit. QSUB_BIN, QSUB_LOG_ROOT, SUBMISSION_ARRAY_MEMORY (16G default),
and SUBMISSION_ARRAY_WALLTIME (24:00:00 default) follow the other array
launchers. APPTAINER_BIN, APPTAINER_EXTRA_ARGS, and APPTAINER_PYTHON_BIN pass
through to each worker.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --submit) SUBMIT=1; shift;;
    --overwrite) OVERWRITE=1; shift;;
    --task-index) TASK_INDEX="$2"; shift 2;;
    --worklist) WORKLIST="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2;;
    *) [[ -z "${INPUT}" ]] || { echo "Only one output directory is allowed" >&2; exit 2; }; INPUT="$1"; shift;;
  esac
done
[[ -n "${INPUT}" && -d "${INPUT}" ]] || { echo "Input must be an existing output directory" >&2; exit 2; }
INPUT="$(cd "${INPUT}" && pwd -P)"
[[ -d "${DIG_DIR}/src/geneset_extractors" ]] || { echo "DIG_REPO/DIG_DIR is not a DIG checkout: ${DIG_DIR}" >&2; exit 1; }
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${INPUT}/qsub_logs_provenance}"
WORKLIST="${WORKLIST:-${QSUB_LOG_ROOT}/provenance_convert_worklist.tsv}"

if [[ -n "${TASK_INDEX}" ]]; then
  row="$(awk -F $'\t' -v task_number="${TASK_INDEX}" 'NR > 1 && $1 == task_number { print; exit }' "${WORKLIST}")"
  [[ -n "${row}" ]] || { echo "No worklist row for task ${TASK_INDEX}" >&2; exit 1; }
  IFS=$'\t' read -r _ provenance <<< "${row}"
  command=(bash "${SCRIPT_DIR}/convert_provenance_apptainer.sh" "${provenance}")
  [[ ${OVERWRITE} -eq 1 ]] && command+=(--overwrite)
  DIG_REPO="${DIG_DIR}" APPTAINER_IMAGE="${APPTAINER_IMAGE}" APPTAINER_BIN="${APPTAINER_BIN}" APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS}" APPTAINER_PYTHON_BIN="${APPTAINER_PYTHON_BIN}" "${command[@]}"
  exit $?
fi

mkdir -p "${QSUB_LOG_ROOT}"
[[ -n "${APPTAINER_IMAGE}" && -f "${APPTAINER_IMAGE}" ]] || { echo "APPTAINER_IMAGE must name an existing image" >&2; exit 1; }
binds="${WRAPPER_DIR},${DIG_DIR},${INPUT}"
discover_command="cd $(printf '%q' "${WRAPPER_DIR}") && exec $(printf '%q' "${APPTAINER_PYTHON_BIN}") -m submission_tools provenance discover $(printf '%q' "${INPUT}") --recursive --dig-python $(printf '%q' "${APPTAINER_PYTHON_BIN}")"
discovery_exec=(env "APPTAINERENV_DIG_REPO=${DIG_DIR}" "${APPTAINER_BIN}" exec --bind "${binds}")
if [[ -n "${APPTAINER_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  extra_args=( ${APPTAINER_EXTRA_ARGS} )
  discovery_exec+=("${extra_args[@]}")
fi
discovery_exec+=("${APPTAINER_IMAGE}" bash --noprofile --norc -c "${discover_command}")
mapfile -t paths < <("${discovery_exec[@]}")
[[ ${#paths[@]} -gt 0 ]] || { echo "No legacy provenance files discovered" >&2; exit 1; }
printf 'task_index\tprovenance_path\n' > "${WORKLIST}"
for index in "${!paths[@]}"; do printf '%s\t%s\n' "$((index + 1))" "${paths[index]}" >> "${WORKLIST}"; done
echo "Provenance worklist written: ${WORKLIST} (${#paths[@]} files)"
[[ ${SUBMIT} -eq 1 ]] || { echo "Set --submit to call qsub."; exit 0; }
environment="PROVENANCE_WORKLIST=${WORKLIST},DIG_REPO=${DIG_DIR},APPTAINER_IMAGE=${APPTAINER_IMAGE},APPTAINER_BIN=${APPTAINER_BIN},APPTAINER_EXTRA_ARGS=${APPTAINER_EXTRA_ARGS},APPTAINER_PYTHON_BIN=${APPTAINER_PYTHON_BIN}"
submit_args=("${INPUT}" --submit)
[[ ${OVERWRITE} -eq 1 ]] && submit_args+=(--overwrite)
exec "${QSUB_BIN}" -N provenance_convert -t "1-${#paths[@]}" \
  -o "${QSUB_LOG_ROOT}/provenance.\$TASK_ID.out" -e "${QSUB_LOG_ROOT}/provenance.\$TASK_ID.err" \
  -l "h_vmem=${SUBMISSION_ARRAY_MEMORY:-16G},h_rt=${SUBMISSION_ARRAY_WALLTIME:-24:00:00}" \
  -v "${environment}" "$0" "${submit_args[@]}"
