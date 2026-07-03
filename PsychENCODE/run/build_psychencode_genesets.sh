#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/PsychENCODE/src/build_psychencode_genesets.py" "$@"
