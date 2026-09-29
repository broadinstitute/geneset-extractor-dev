#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
shift || true
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

exec "${PYTHON_BIN:-python3}" "${root}/src/dispatch_gtex_submission.py" "$@" -- "${mode}"
