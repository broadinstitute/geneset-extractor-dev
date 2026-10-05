#!/usr/bin/env bash
# Thin modern adapter for the established MoTrPAC Apptainer array launcher.
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
legacy_launcher="${root}/../run/submit_motrpac_models_cluster_apptainer.sh"
mode="--full"
submit=0
refresh=0
model_id=""
tissue_id=""
model_group=""
array_memory="${SUBMISSION_ARRAY_MEMORY:-${MOTRPAC_ARRAY_MEMORY:-16G}}"
array_walltime="${SUBMISSION_ARRAY_WALLTIME:-${MOTRPAC_ARRAY_WALLTIME:-24:00:00}}"
smoke_memory="${SUBMISSION_SMOKE_MEMORY:-${MOTRPAC_SUBMISSION_MEMORY:-4G}}"
smoke_walltime="${SUBMISSION_SMOKE_WALLTIME:-${MOTRPAC_SUBMISSION_WALLTIME:-01:00:00}}"

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh [--smoke|--full] [--model-id ID[,ID...]] [--tissue-id ID] [--model-group TR|TW|HZ] [--refresh-metadata-and-provenance] [--submit]

--full delegates to the established MoTrPAC Apptainer array launcher. --smoke
runs the committed HZ1 fixture as one Apptainer job only with --submit.
Set SUBMISSION_WORK_DIR outside the checkout, APPTAINER_IMAGE, DIG_REPO, and
the full inputs declared in reproduction/input_manifest.tsv. Full resource
settings are SUBMISSION_ARRAY_MEMORY and SUBMISSION_ARRAY_WALLTIME; smoke
resource settings are SUBMISSION_SMOKE_MEMORY and SUBMISSION_SMOKE_WALLTIME.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke) mode="--smoke" ;;
    --full) mode="--full" ;;
    --submit) submit=1 ;;
    --refresh-metadata-and-provenance|--refresh_metadata_and_provenance) refresh=1 ;;
    --model-id) [[ $# -ge 2 ]] || { echo "Missing value for --model-id" >&2; exit 2; }; model_id="$2"; shift ;;
    --tissue-id) [[ $# -ge 2 ]] || { echo "Missing value for --tissue-id" >&2; exit 2; }; tissue_id="$2"; shift ;;
    --model-group) [[ $# -ge 2 ]] || { echo "Missing value for --model-group" >&2; exit 2; }; model_group="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the MoTrPAC checkout" >&2; exit 1; }
mkdir -p "${SUBMISSION_WORK_DIR}"
if [[ ${refresh} -eq 1 ]]; then
  [[ "${mode}" == "--full" ]] || { echo "Refresh requires --full" >&2; exit 2; }
  command=(bash "${root}/run/refresh_submission_models_apptainer.sh")
  [[ -n "${model_id}" ]] && command+=(--model-id "${model_id}")
  [[ -n "${tissue_id}" ]] && command+=(--partition-id "${tissue_id}")
  [[ ${submit} -eq 1 ]] && command+=(--submit)
  exec "${command[@]}"
fi
if [[ "${mode}" == "--smoke" ]]; then
  [[ -z "${model_id}${tissue_id}${model_group}" ]] || { echo "model and tissue filters are supported only with --full" >&2; exit 2; }
  if [[ ${submit} -eq 0 ]]; then
    echo "Would run one smoke job through run_submission_models_apptainer.sh. Set --submit to call qsub."
    exit 0
  fi
  mkdir -p "${SUBMISSION_WORK_DIR}/qsub_logs"
  exec "${QSUB_BIN:-qsub}" -N "motrpac_submission_smoke" -o "${SUBMISSION_WORK_DIR}/qsub_logs/motrpac_submission_smoke.out" -e "${SUBMISSION_WORK_DIR}/qsub_logs/motrpac_submission_smoke.err" -l "h_vmem=${smoke_memory},h_rt=${smoke_walltime}" bash "${root}/run/run_submission_models_apptainer.sh" --smoke
fi

command=(env "WORK_ROOT=${SUBMISSION_WORK_DIR}" "MOTRPAC_OUT_ROOT=${SUBMISSION_WORK_DIR}" "DIG_DIR=${DIG_REPO:-}" "MOTRPAC_ARRAY_MEMORY=${array_memory}" "MOTRPAC_ARRAY_WALLTIME=${array_walltime}" "MOTRPAC_RAW_COUNTS_DIR=${MOTRPAC_RAW_COUNTS_DIR:-}" "MOTRPAC_TRANSCRIPT_METADATA_TSV=${MOTRPAC_TRANSCRIPT_METADATA_TSV:-}" "MOTRPAC_PHENOTYPE_METADATA_TSV=${MOTRPAC_PHENOTYPE_METADATA_TSV:-}" "MOTRPAC_FEATURE_TO_GENE_TSV=${MOTRPAC_FEATURE_TO_GENE_TSV:-}" "MOTRPAC_RAT_TO_HUMAN_TSV=${MOTRPAC_RAT_TO_HUMAN_TSV:-}" "MOTRPAC_FEATURE_ANNOT=${MOTRPAC_FEATURE_ANNOT:-}" "MOTRPAC_DEA_DIR=${MOTRPAC_DEA_DIR:-}" "MOTRPAC_MAPPING_FILE=${MOTRPAC_MAPPING_FILE:-}" "${legacy_launcher}" --submit)
[[ -n "${model_id}" ]] && command+=(--model_id "${model_id}")
[[ -n "${tissue_id}" ]] && command+=(--tissue_id "${tissue_id}")
[[ -n "${model_group}" ]] && command+=(--model_group "${model_group}")
if [[ ${submit} -eq 0 ]]; then
  printf 'Would submit MoTrPAC array: '; printf '%q ' "${command[@]}"; printf '\nSet --submit to call qsub.\n'
  exit 0
fi
exec "${command[@]}"
