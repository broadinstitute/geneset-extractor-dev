#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GTEX_ROOT="${REPO_ROOT}/geneset-extractor-dev/GTEx"
PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "${PYTHON_BIN}" "${GTEX_ROOT}/src/write_gmt_command_markdown.py" "$@"
