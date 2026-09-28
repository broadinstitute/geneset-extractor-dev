#!/usr/bin/env bash
# Submit the complete declared GTEx model matrix through the established array launcher.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
legacy_launcher="${root}/../run/submit_gtex_models_cluster_apptainer.sh"
mode="full"
submit=0

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--submit]

--full delegates to the established GTEx Apptainer array launcher with the
modern declared inputs and SUBMISSION_WORK_DIR. It creates one task for every
enabled model and broad-tissue partition (currently 990 tasks). Without
--submit, it prints the delegated command and never calls qsub. --smoke runs
the small declared smoke reproduction as one Apptainer job only with --submit.

Required environment: APPTAINER_IMAGE, DIG_REPO, SUBMISSION_WORK_DIR.
Full mode additionally requires GTEX_V10_COUNTS_GCT,
GTEX_V10_SAMPLE_ATTRIBUTES_TSV, GTEX_V10_SUBJECT_PHENOTYPES_TSV,
GTEX_V8_COUNTS_GCT, GTEX_V8_SAMPLE_ATTRIBUTES_TSV,
GTEX_V8_SUBJECT_PHENOTYPES_TSV, GTEX_V8_HUMAN_GENE_INFO, and GTEX_GTF.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke) mode="--smoke" ;;
    --full) mode="full" ;;
    --submit) submit=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GTEx checkout" >&2; exit 1; }
if [[ "${mode}" == "--smoke" ]]; then
  if [[ ${submit} -eq 0 ]]; then
    echo "Would run one smoke job through run_submission_models_apptainer.sh. Set --submit to call qsub."
    exit 0
  fi
  mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
  exec "${QSUB_BIN:-qsub}" -N "${GTEX_SUBMISSION_JOB_NAME:-gtex_submission_smoke}" \
    -o "${SUBMISSION_WORK_DIR}/qsub_logs/gtex_submission_smoke.out" \
    -e "${SUBMISSION_WORK_DIR}/qsub_logs/gtex_submission_smoke.err" \
    -l "h_vmem=${GTEX_SUBMISSION_MEMORY:-4G},h_rt=${GTEX_SUBMISSION_WALLTIME:-01:00:00}" \
    bash "${root}/run/run_submission_models_apptainer.sh" --smoke
fi

command=(env "WORK_ROOT=${SUBMISSION_WORK_DIR}" "GTEX_OUT_ROOT=${SUBMISSION_WORK_DIR}" "DIG_DIR=${DIG_REPO:-}" \
  "GTEX_V10_COUNTS_GCT=${GTEX_V10_COUNTS_GCT:-}" "GTEX_V10_SAMPLE_ATTRIBUTES_TSV=${GTEX_V10_SAMPLE_ATTRIBUTES_TSV:-}" "GTEX_V10_SUBJECT_PHENOTYPES_TSV=${GTEX_V10_SUBJECT_PHENOTYPES_TSV:-}" \
  "GTEX_V8_COUNTS_GCT=${GTEX_V8_COUNTS_GCT:-}" "GTEX_V8_SAMPLE_ATTRIBUTES_TSV=${GTEX_V8_SAMPLE_ATTRIBUTES_TSV:-}" "GTEX_V8_SUBJECT_PHENOTYPES_TSV=${GTEX_V8_SUBJECT_PHENOTYPES_TSV:-}" "GTEX_V8_HUMAN_GENE_INFO=${GTEX_V8_HUMAN_GENE_INFO:-}" "GTEX_GTF=${GTEX_GTF:-}" \
  "${legacy_launcher}" --submit)
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit complete 990-task GTEx array: '
  printf '%q ' "${command[@]}"
  printf '\nSet --submit to call qsub.\n'
  exit 0
fi

[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "--submit requires APPTAINER_IMAGE" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "--submit requires DIG_REPO" >&2; exit 1; }
for variable in GTEX_V10_COUNTS_GCT GTEX_V10_SAMPLE_ATTRIBUTES_TSV GTEX_V10_SUBJECT_PHENOTYPES_TSV GTEX_V8_COUNTS_GCT GTEX_V8_SAMPLE_ATTRIBUTES_TSV GTEX_V8_SUBJECT_PHENOTYPES_TSV GTEX_V8_HUMAN_GENE_INFO GTEX_GTF; do
  [[ -n "${!variable:-}" && -f "${!variable}" ]] || { echo "--submit requires existing ${variable}" >&2; exit 1; }
done
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
exec "${command[@]}"
