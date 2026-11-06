#!/usr/bin/env bash
# Submit declared GTEx task-manifest rows through the shared launcher.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "${root}/../.." && pwd)"
submit=0
model_id=""
partition_id=""
skip_evaluation=0
evaluation_references=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full) shift ;;
    --submit) submit=1; shift ;;
    --model-id) model_id="$2"; shift 2 ;;
    --partition-id|--tissue-id) partition_id="$2"; shift 2 ;;
    --evaluation-reference) evaluation_references+=("$2"); shift 2 ;;
    --skip-evaluation) skip_evaluation=1; shift ;;
    -h|--help) echo "usage: $0 --full [--model-id ID[,ID...]] [--partition-id ID] [--submit]"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR" >&2; exit 1; }
if [[ $skip_evaluation -eq 0 && ${#evaluation_references[@]} -eq 0 ]]; then
  echo "--evaluation-reference is required unless --skip-evaluation is used" >&2
  exit 2
fi
export GENESET_SKIP_EVALUATION="$skip_evaluation"
export GENESET_EVALUATION_REFERENCES="$(IFS=:; echo "${evaluation_references[*]}")"
export SUBMISSION_ARRAY_MEMORY="${SUBMISSION_ARRAY_MEMORY:-${GTEX_ARRAY_MEMORY:-16G}}"
export SUBMISSION_ARRAY_WALLTIME="${SUBMISSION_ARRAY_WALLTIME:-${GTEX_ARRAY_WALLTIME:-24:00:00}}"
command=(bash "${repo_root}/geneset-extractor-dev/run/submit_library_models_cluster_apptainer.sh"
  --library-id GTEx --library-root "${root}" --task-manifest "${root}/config/task_manifest.tsv")
[[ -n "$model_id" ]] && command+=(--model-id "$model_id")
[[ -n "$partition_id" ]] && command+=(--partition-id "$partition_id")
[[ $submit -eq 1 ]] && command+=(--submit)
exec "${command[@]}"
