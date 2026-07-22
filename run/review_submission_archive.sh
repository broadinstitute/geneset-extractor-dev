#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONPATH="${REPO_ROOT}/geneset-extractor-dev/src${PYTHONPATH:+:${PYTHONPATH}}"

exec "${PYTHON_BIN}" -m review_submission_archive "$@"
