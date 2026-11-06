#!/usr/bin/env bash
# Backward-compatible name for the shared library task launcher.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${script_dir}/submit_library_tasks_apptainer.sh" "$@"
