#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/MoTrPAC/src/build_motrpac_genesets.py" "$@"
