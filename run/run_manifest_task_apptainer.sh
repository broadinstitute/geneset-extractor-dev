#!/usr/bin/env bash
set -euo pipefail

apptainer_bin=""
bind_csv=""
image=""
launcher=""
extra_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apptainer-bin) apptainer_bin="$2"; shift 2 ;;
    --bind) bind_csv="$2"; shift 2 ;;
    --image) image="$2"; shift 2 ;;
    --launcher) launcher="$2"; shift 2 ;;
    --extra-arg) extra_args+=("$2"); shift 2 ;;
    --) shift; break ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$apptainer_bin" && -n "$bind_csv" && -n "$image" && -n "$launcher" ]] || exit 2
[[ -n "${SGE_TASK_ID:-}" ]] || { echo "Missing SGE_TASK_ID" >&2; exit 1; }
exec "$apptainer_bin" exec --bind "$bind_csv" "${extra_args[@]}" "$image" "$launcher" \
  --task-index "$SGE_TASK_ID" "$@"
