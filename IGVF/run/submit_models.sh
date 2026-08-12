#!/usr/bin/env bash
set -euo pipefail
exec "${PYTHON_BIN:-python3}" src/build_igvf_genesets.py "$@"
