#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
shift || true
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"

case "${mode}" in
  --smoke|full) ;;
  --full) mode="full" ;;
  *) echo "usage: run_submission_models.sh [--smoke|--full]" >&2; exit 2 ;;
esac

exec "${PYTHON_BIN:-python3}" "${root}/src/dispatch_gtex_submission.py" "$@" -- "${mode}"
