#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
exec "${PYTHON_BIN:-python3}" "${repo_root}/geneset-extractor-dev/src/evaluate_gmt_chunks.py" --task-index "${SGE_TASK_ID:?missing SGE_TASK_ID}" "$@"
