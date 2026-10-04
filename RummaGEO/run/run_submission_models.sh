#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec "${PYTHON_BIN:-python3}" "${root}/src/dispatch_rummageo_submission.py" "$@"
