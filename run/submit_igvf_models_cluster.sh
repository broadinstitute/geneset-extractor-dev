#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WRAPPER_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
exec "${WRAPPER_ROOT}/run/submit_library_models_cluster.sh" --library-id IGVF --library-root "${WRAPPER_ROOT}/IGVF" --task-manifest "${WRAPPER_ROOT}/IGVF/config/task_manifest.tsv" "$@"
