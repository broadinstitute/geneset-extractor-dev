#!/usr/bin/env bash
# Submit the complete declared GTEx model matrix through the established array launcher.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
legacy_launcher="${root}/../run/submit_gtex_models_cluster_apptainer.sh"
mode="full"
submit=0
refresh=0
model_id=""
tissue_id=""
array_memory="${SUBMISSION_ARRAY_MEMORY:-${GTEX_ARRAY_MEMORY:-16G}}"
array_walltime="${SUBMISSION_ARRAY_WALLTIME:-${GTEX_ARRAY_WALLTIME:-24:00:00}}"
array_job_name="${SUBMISSION_JOB_NAME:-${GTEX_JOB_NAME:-gtex_submission_apptainer}}"
smoke_memory="${SUBMISSION_SMOKE_MEMORY:-${GTEX_SUBMISSION_MEMORY:-4G}}"
smoke_walltime="${SUBMISSION_SMOKE_WALLTIME:-${GTEX_SUBMISSION_WALLTIME:-01:00:00}}"
smoke_job_name="${SUBMISSION_SMOKE_JOB_NAME:-${GTEX_SUBMISSION_JOB_NAME:-gtex_submission_smoke}}"

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--model-id ID[,ID...]] [--tissue-id ID] [--refresh-metadata-and-provenance] [--submit]

--full delegates to the established GTEx Apptainer array launcher with the
modern declared inputs and SUBMISSION_WORK_DIR. It creates one task for every
enabled model and broad-tissue partition (currently 990 tasks). Without
--submit, it prints the delegated command and never calls qsub. --smoke runs
the small declared smoke reproduction as one Apptainer job only with --submit.
Use --model-id to select one or more enabled GTEx model IDs and --tissue-id to
select one configured broad-tissue partition. HZ2 can be combined with other
model IDs; it is submitted as its dedicated consensus task while the remaining
IDs are submitted through the standard model-by-tissue array.

Required environment: APPTAINER_IMAGE, DIG_REPO, SUBMISSION_WORK_DIR.
Full mode additionally requires GTEX_V10_COUNTS_GCT,
GTEX_V10_SAMPLE_ATTRIBUTES_TSV, GTEX_V10_SUBJECT_PHENOTYPES_TSV,
GTEX_V8_COUNTS_GCT, GTEX_V8_SAMPLE_ATTRIBUTES_TSV,
GTEX_V8_SUBJECT_PHENOTYPES_TSV, GTEX_V8_HUMAN_GENE_INFO, and GTEX_GTF.

Resource settings: SUBMISSION_ARRAY_MEMORY, SUBMISSION_ARRAY_WALLTIME, and
SUBMISSION_JOB_NAME for full arrays; SUBMISSION_SMOKE_MEMORY,
SUBMISSION_SMOKE_WALLTIME, and SUBMISSION_SMOKE_JOB_NAME for smoke jobs.
Legacy GTEX_* resource variables remain fallbacks only.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke) mode="--smoke" ;;
    --full) mode="full" ;;
    --submit) submit=1 ;;
    --refresh-metadata-and-provenance|--refresh_metadata_and_provenance) refresh=1 ;;
    --model-id) [[ $# -ge 2 ]] || { echo "Missing value for --model-id" >&2; exit 2; }; model_id="$2"; shift ;;
    --tissue-id) [[ $# -ge 2 ]] || { echo "Missing value for --tissue-id" >&2; exit 2; }; tissue_id="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GTEx checkout" >&2; exit 1; }
if [[ ${refresh} -eq 1 ]]; then
  [[ "${mode}" == "full" ]] || { echo "Refresh requires --full" >&2; exit 2; }
  command=(bash "${root}/run/refresh_submission_models_apptainer.sh")
  [[ -n "${model_id}" ]] && command+=(--model-id "${model_id}")
  [[ -n "${tissue_id}" ]] && command+=(--partition-id "${tissue_id}")
  [[ ${submit} -eq 1 ]] && command+=(--submit)
  exec "${command[@]}"
fi
if [[ "${mode}" == "--smoke" ]]; then
  [[ -z "${model_id}" && -z "${tissue_id}" ]] || { echo "--model-id and --tissue-id are supported only with --full" >&2; exit 2; }
  if [[ ${submit} -eq 0 ]]; then
    echo "Would run one smoke job through run_submission_models_apptainer.sh. Set --submit to call qsub."
    exit 0
  fi
  mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
  exec "${QSUB_BIN:-qsub}" -N "${smoke_job_name}" \
    -o "${SUBMISSION_WORK_DIR}/qsub_logs/gtex_submission_smoke.out" \
    -e "${SUBMISSION_WORK_DIR}/qsub_logs/gtex_submission_smoke.err" \
    -l "h_vmem=${smoke_memory},h_rt=${smoke_walltime}" \
    bash "${root}/run/run_submission_models_apptainer.sh" --smoke
fi

for requested_model in ${model_id//,/ }; do
  awk -F $'\t' -v model="${requested_model}" 'NR > 1 && $1 == model && $3 == "true" { found = 1 } END { exit !found }' "${root}/config/model_list.tsv" \
    || { echo "Unknown or disabled GTEx model ID: ${requested_model}" >&2; exit 2; }
done
if [[ -n "${tissue_id}" ]]; then
  awk -F $'\t' -v tissue="${tissue_id}" 'NR > 1 && $1 == tissue { found = 1 } END { exit !found }' "${root}/config/broad_tissue_list.tsv" \
    || { echo "Unknown GTEx broad tissue ID: ${tissue_id}" >&2; exit 2; }
fi

# HZ2 has a distinct input contract and no broad-tissue partition.  Keep it as
# a dedicated job, but allow callers to select it alongside standard models in
# one command.  The standard array receives only the remaining model IDs.
hz2_requested=0
standard_model_ids=()
if [[ -z "${model_id}" ]]; then
  hz2_requested=1
else
  IFS=',' read -r -a requested_model_ids <<< "${model_id}"
  for requested_model in "${requested_model_ids[@]}"; do
    requested_model="${requested_model//[[:space:]]/}"
    [[ -n "${requested_model}" ]] || continue
    if [[ "${requested_model}" == "HZ2" ]]; then
      hz2_requested=1
    else
      standard_model_ids+=("${requested_model}")
    fi
  done
fi
if [[ ${hz2_requested} -eq 1 && -n "${tissue_id}" ]]; then
  echo "HZ2 has no broad-tissue partition; omit --tissue-id when selecting HZ2" >&2
  exit 2
fi
standard_model_id=""
if [[ ${#standard_model_ids[@]} -gt 0 ]]; then
  standard_model_id="$(IFS=,; echo "${standard_model_ids[*]}")"
fi

submit_hz2() {
  local runner="${root}/run/run_hz2_task_apptainer.sh"
  [[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "--submit requires APPTAINER_IMAGE" >&2; return 1; }
  [[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "--submit requires DIG_REPO" >&2; return 1; }
  for variable in GTEX_V8_TPM_GCT GTEX_V8_SAMPLE_ATTRIBUTES_TSV GTEX_V8_SUBJECT_PHENOTYPES_TSV; do [[ -n "${!variable:-}" && -f "${!variable}" ]] || { echo "--submit requires existing ${variable}" >&2; return 1; }; done
  mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
  export_vars="GTEX_WRAPPER_ROOT=${root},SUBMISSION_WORK_DIR=${SUBMISSION_WORK_DIR},DIG_REPO=${DIG_REPO},APPTAINER_IMAGE=${APPTAINER_IMAGE},GTEX_V8_TPM_GCT=${GTEX_V8_TPM_GCT},GTEX_V8_SAMPLE_ATTRIBUTES_TSV=${GTEX_V8_SAMPLE_ATTRIBUTES_TSV},GTEX_V8_SUBJECT_PHENOTYPES_TSV=${GTEX_V8_SUBJECT_PHENOTYPES_TSV}"
  "${QSUB_BIN:-qsub}" -N "${array_job_name}_hz2" -o "${SUBMISSION_WORK_DIR}/qsub_logs/gtex_hz2.out" -e "${SUBMISSION_WORK_DIR}/qsub_logs/gtex_hz2.err" -l "h_vmem=${array_memory},h_rt=${array_walltime}" -v "${export_vars}" "${runner}" full
}
if [[ ${hz2_requested} -eq 1 && -z "${standard_model_id}" ]]; then
  if [[ ${submit} -eq 0 ]]; then echo "Would submit one HZ2 consensus task through run_hz2_task_apptainer.sh. Set --submit to call qsub."; exit 0; fi
  submit_hz2; exit $?
fi

command=(env "WORK_ROOT=${SUBMISSION_WORK_DIR}" "GTEX_OUT_ROOT=${SUBMISSION_WORK_DIR}" "DIG_DIR=${DIG_REPO:-}" \
  "GTEX_ARRAY_MEMORY=${array_memory}" "GTEX_ARRAY_WALLTIME=${array_walltime}" "GTEX_JOB_NAME=${array_job_name}" \
  "GTEX_V10_COUNTS_GCT=${GTEX_V10_COUNTS_GCT:-}" "GTEX_V10_SAMPLE_ATTRIBUTES_TSV=${GTEX_V10_SAMPLE_ATTRIBUTES_TSV:-}" "GTEX_V10_SUBJECT_PHENOTYPES_TSV=${GTEX_V10_SUBJECT_PHENOTYPES_TSV:-}" \
  "GTEX_V8_COUNTS_GCT=${GTEX_V8_COUNTS_GCT:-}" "GTEX_V8_SAMPLE_ATTRIBUTES_TSV=${GTEX_V8_SAMPLE_ATTRIBUTES_TSV:-}" "GTEX_V8_SUBJECT_PHENOTYPES_TSV=${GTEX_V8_SUBJECT_PHENOTYPES_TSV:-}" "GTEX_V8_HUMAN_GENE_INFO=${GTEX_V8_HUMAN_GENE_INFO:-}" "GTEX_GTF=${GTEX_GTF:-}" \
  "${legacy_launcher}" --submit)
[[ -n "${standard_model_id}" ]] && command+=(--model_id "${standard_model_id}")
[[ -n "${tissue_id}" ]] && command+=(--tissue_id "${tissue_id}")
if [[ ${submit} -eq 0 ]]; then
  if [[ ${hz2_requested} -eq 1 ]]; then echo "Would also submit one HZ2 consensus task through run_hz2_task_apptainer.sh."; fi
  printf 'Would submit GTEx array: '
  printf '%q ' "${command[@]}"
  printf '\nSet --submit to call qsub.\n'
  exit 0
fi

[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "--submit requires APPTAINER_IMAGE" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "--submit requires DIG_REPO" >&2; exit 1; }
for variable in GTEX_V10_COUNTS_GCT GTEX_V10_SAMPLE_ATTRIBUTES_TSV GTEX_V10_SUBJECT_PHENOTYPES_TSV GTEX_V8_COUNTS_GCT GTEX_V8_SAMPLE_ATTRIBUTES_TSV GTEX_V8_SUBJECT_PHENOTYPES_TSV GTEX_V8_HUMAN_GENE_INFO GTEX_GTF; do
  [[ -n "${!variable:-}" && -f "${!variable}" ]] || { echo "--submit requires existing ${variable}" >&2; exit 1; }
done
if [[ ${hz2_requested} -eq 1 ]]; then submit_hz2; fi
mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
exec "${command[@]}"
