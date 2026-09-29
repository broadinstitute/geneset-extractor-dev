#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec "${PYTHON_BIN:-python3}" "${root}/src/dispatch_lincs_l1000_submission.py" "$@"
