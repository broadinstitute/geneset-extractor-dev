#!/usr/bin/env bash
set -euo pipefail
mode="${1:---smoke}"
if [[ "${mode}" == "--smoke" ]]; then exit 0; fi
echo "GlyGen full inputs are explicit snapshots; set the variables documented in input_manifest.tsv." >&2
