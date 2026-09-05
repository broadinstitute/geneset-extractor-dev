#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
LIBRARY_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
mode="${1:?usage: build_igvf_genesets.sh --smoke|full --out-root PATH}"
shift
[[ "${mode}" == "--smoke" ]] && mode="smoke"
exec "${PYTHON_BIN:-python3}" "${LIBRARY_ROOT}/src/run_igvf_task.py" "$@" "${mode}"
