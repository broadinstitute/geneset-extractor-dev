#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
mode="${1:---smoke}"
shift || true
exec "${PYTHON_BIN:-python3}" "${root}/src/run_gtex_task.py" "$@" -- "${mode}"
