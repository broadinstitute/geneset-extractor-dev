#!/usr/bin/env bash
# Generic, configuration-driven cluster launcher for new-format libraries.
set -euo pipefail

SELF_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

LIBRARY_ID=""
LIBRARY_ROOT=""
TASK_MANIFEST=""
SUBMIT=0
TASK_ID=""
MODEL_ID=""
PARTITION_ID=""
TASK_INDEX="${SGE_TASK_ID:-}"
# Scheduler worklists and generated artifacts must remain outside the wrapper
# checkout. SUBMISSION_WORK_DIR is the standard adoption/workspace setting;
# WORK_ROOT is retained for explicit scheduler-only overrides.
WORK_ROOT="${SUBMISSION_WORK_DIR:-${WORK_ROOT:-}}"
QSUB_BIN="${QSUB_BIN:-qsub}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
EXECUTION_MODE="apptainer"
PROFILE_ENVIRONMENT=()
RESOURCE_ARGS=()

usage() {
  cat <<'EOF'
Usage: submit_library_models_cluster_apptainer.sh --library-id ID --library-root PATH --task-manifest PATH [--submit] [--task-id ID] [--model-id ID] [--partition-id ID]

Without --submit, write and print the filtered worklist only. --submit is the
only mode that calls qsub. Array tasks re-enter this script and invoke the
library's canonical local builder for exactly one task. The native shared
launcher sets the internal --execution-mode native option.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --library-id|--library-root|--task-manifest|--task-id|--model-id|--partition-id|--task-index|--execution-mode)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --library-id) LIBRARY_ID="$2" ;; --library-root) LIBRARY_ROOT="$2" ;;
        --task-manifest) TASK_MANIFEST="$2" ;; --task-id) TASK_ID="$2" ;;
        --model-id) MODEL_ID="$2" ;; --partition-id) PARTITION_ID="$2" ;;
        --task-index) TASK_INDEX="$2" ;;
        --execution-mode) EXECUTION_MODE="$2" ;;
      esac
      shift 2 ;;
    --submit) SUBMIT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$LIBRARY_ID" && -n "$LIBRARY_ROOT" && -n "$TASK_MANIFEST" ]] || { usage >&2; exit 2; }
[[ "$EXECUTION_MODE" == "apptainer" || "$EXECUTION_MODE" == "native" ]] || { echo "--execution-mode must be apptainer or native" >&2; exit 2; }
[[ -n "$WORK_ROOT" ]] || { echo "Set SUBMISSION_WORK_DIR (or explicit WORK_ROOT) outside the wrapper checkout" >&2; exit 2; }
[[ -n "${SUBMISSION_ARRAY_MEMORY:-}" ]] && RESOURCE_ARGS+=(-l "h_vmem=${SUBMISSION_ARRAY_MEMORY}")
[[ -n "${SUBMISSION_ARRAY_WALLTIME:-}" ]] && RESOURCE_ARGS+=(-l "h_rt=${SUBMISSION_ARRAY_WALLTIME}")
[[ -f "$TASK_MANIFEST" ]] || { echo "Missing task manifest: $TASK_MANIFEST" >&2; exit 1; }
builder="$LIBRARY_ROOT/run/build_$(tr '[:upper:]-' '[:lower:]_' <<< "$LIBRARY_ID")_genesets.sh"
[[ -x "$builder" ]] || { echo "Missing executable local builder: $builder" >&2; exit 1; }

profile="$LIBRARY_ROOT/config/execution_profile.tsv"
if [[ -f "$profile" ]]; then
  while IFS=$'\t' read -r variable required path_type; do
    [[ "$variable" == "environment_variable" ]] && continue
    [[ "$required" == "true" ]] || continue
    [[ -n "${!variable:-}" ]] || { echo "Missing required ${LIBRARY_ID} input: ${variable}" >&2; exit 1; }
    if [[ "$path_type" == "directory" ]]; then
      [[ -d "${!variable}" ]] || { echo "Expected directory for ${variable}: ${!variable}" >&2; exit 1; }
    else
      [[ -f "${!variable}" ]] || { echo "Expected file for ${variable}: ${!variable}" >&2; exit 1; }
    fi
    PROFILE_ENVIRONMENT+=("${variable}=${!variable}")
  done < "$profile"
fi

mkdir -p "$WORK_ROOT"
worklist="$WORK_ROOT/${LIBRARY_ID,,}_worklist.tsv"
awk -F $'\t' -v task="$TASK_ID" -v model="$MODEL_ID" -v partition="$PARTITION_ID" '
  NR == 1 { for (i=1;i<=NF;i++) col[$i]=i; print "task_index\ttask_id\tmodel_id\tpartition_id\tdig_identifier\toutput_relative_path"; next }
  $(col["enabled"]) == "true" && (!task || $(col["task_id"]) == task) && (!model || ("," model ",") ~ ("," $(col["model_id"]) ",")) && (!partition || $(col["partition_id"]) == partition) {
    print ++n "\t" $(col["task_id"]) "\t" $(col["model_id"]) "\t" $(col["partition_id"]) "\t" $(col["dig_identifier"]) "\t" $(col["output_relative_path"])
  }
' "$TASK_MANIFEST" > "$worklist"
[[ $(wc -l < "$worklist") -gt 1 ]] || { echo "No enabled tasks matched requested filters" >&2; exit 1; }

if [[ -n "$TASK_INDEX" ]]; then
  task_id=$(awk -F $'\t' -v task_number="$TASK_INDEX" 'NR > 1 && $1 == task_number {print $2; exit}' "$worklist")
  [[ -n "$task_id" ]] || { echo "No task for array index $TASK_INDEX" >&2; exit 1; }
  exec env "${PROFILE_ENVIRONMENT[@]}" bash "$builder" full --task-id "$task_id" --out-root "$WORK_ROOT"
fi

if [[ $SUBMIT -eq 0 ]]; then
  echo "Worklist written: $worklist"
  exit 0
fi
task_count=$(( $(wc -l < "$worklist") - 1 ))
qsub_log_root="$WORK_ROOT/qsub_logs_${LIBRARY_ID,,}"
mkdir -p "$qsub_log_root"
if [[ "$EXECUTION_MODE" == "native" ]]; then
  profile_csv="WORK_ROOT=${WORK_ROOT},SUBMISSION_WORK_DIR=${WORK_ROOT}"
  for assignment in "${PROFILE_ENVIRONMENT[@]}"; do
    profile_csv+=",${assignment}"
  done
  native_env_args=()
  [[ -n "$profile_csv" ]] && native_env_args=(-v "$profile_csv")
  exec "$QSUB_BIN" -N "${LIBRARY_ID,,}_manifest" -o "$qsub_log_root" -e "$qsub_log_root" "${RESOURCE_ARGS[@]}" -t "1-${task_count}" "${native_env_args[@]}" "$SELF_PATH" \
    --execution-mode native --library-id "$LIBRARY_ID" --library-root "$LIBRARY_ROOT" --task-manifest "$TASK_MANIFEST" \
    --submit
fi
[[ -n "$APPTAINER_IMAGE" && -f "$APPTAINER_IMAGE" ]] || { echo "--submit requires APPTAINER_IMAGE" >&2; exit 1; }
APPTAINER_BIN="$(command -v "$APPTAINER_BIN")" || { echo "Unable to find APPTAINER_BIN: ${APPTAINER_BIN}" >&2; exit 1; }
profile_csv="GENESET_EXTRACTORS_IN_APPTAINER=1,WORK_ROOT=${WORK_ROOT},SUBMISSION_WORK_DIR=${WORK_ROOT},APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1,APPTAINERENV_WORK_ROOT=${WORK_ROOT},APPTAINERENV_SUBMISSION_WORK_DIR=${WORK_ROOT}"
for assignment in "${PROFILE_ENVIRONMENT[@]}"; do
  profile_csv+=",${assignment},APPTAINERENV_${assignment}"
done
for runtime_variable in PYTHON_BIN RSCRIPT_BIN APPTAINER_PYTHON_BIN APPTAINER_RSCRIPT_BIN PROVENANCE_MIRROR_LOCAL_PREFIX PROVENANCE_MIRROR_REMOTE_PREFIX LOCAL_INPUT_SOURCE_MAP_TSV; do
  [[ -n "${!runtime_variable:-}" ]] || continue
  profile_csv+=",${runtime_variable}=${!runtime_variable},APPTAINERENV_${runtime_variable}=${!runtime_variable}"
done
bind_paths=("$(pwd)" "$WORK_ROOT" "$LIBRARY_ROOT" "$(dirname "$SELF_PATH")")
for assignment in "${PROFILE_ENVIRONMENT[@]}"; do
  input_path="${assignment#*=}"
  if [[ -d "$input_path" ]]; then bind_paths+=("$input_path"); else bind_paths+=("$(dirname "$input_path")"); fi
done
for path_variable in PROVENANCE_MIRROR_LOCAL_PREFIX LOCAL_INPUT_SOURCE_MAP_TSV; do
  [[ -n "${!path_variable:-}" ]] || continue
  path_value="${!path_variable}"
  [[ -e "$path_value" ]] && bind_paths+=("$( [[ -d "$path_value" ]] && printf '%s' "$path_value" || dirname "$path_value" )")
done
bind_csv="$(printf '%s\n' "${bind_paths[@]}" | awk '!seen[$0]++' | paste -sd, -)"
extra_args=()
if [[ -n "${APPTAINER_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=(${APPTAINER_EXTRA_ARGS})
fi
exec "$QSUB_BIN" -N "${LIBRARY_ID,,}_manifest" -o "$qsub_log_root" -e "$qsub_log_root" "${RESOURCE_ARGS[@]}" -b y -t "1-${task_count}" -v "$profile_csv" \
  "$APPTAINER_BIN" exec --bind "$bind_csv" "${extra_args[@]}" "$APPTAINER_IMAGE" "$SELF_PATH" \
  --execution-mode apptainer --library-id "$LIBRARY_ID" --library-root "$LIBRARY_ROOT" --task-manifest "$TASK_MANIFEST" \
  --submit
