#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GlyGen checkout" >&2; exit 1; }
exec bash "${root}/../run/refresh_library_models_cluster_apptainer.sh" \
  --library-id GlyGen --library-root "${root}" --out-root "${SUBMISSION_WORK_DIR}" \
  --refresh-metadata-and-provenance "$@"
