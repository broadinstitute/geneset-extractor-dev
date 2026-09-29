#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke) exit 0 ;;
  full)
    for name in LINCS_CHEMPERT_EXPRESSION_TSV LINCS_CRISPRKO_EXPRESSION_TSV LINCS_MAPPING_FILE; do
      [[ -n "${!name:-}" && -f "${!name}" ]] || { echo "Set ${name} to an existing declared input; see input_manifest.tsv" >&2; exit 1; }
    done
    ;;
  *) echo "usage: download_inputs.sh [--smoke|full]" >&2; exit 2 ;;
esac
