#!/usr/bin/env bash
# Native scheduler entry point. The shared launcher owns all task handling.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "${SCRIPT_DIR}/submit_library_models_cluster_apptainer.sh" --execution-mode native "$@"
