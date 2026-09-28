#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
mode="${1:?usage: build_gtex_models.sh --smoke|full --out-root PATH}"
shift
exec "${PYTHON_BIN:-python3}" "${root}/modern/src/dispatch_gtex_task.py" "$@" -- "${mode}"
