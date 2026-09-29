#!/usr/bin/env bash
set -euo pipefail
mode="${1:---smoke}"
case "${mode}" in
  --smoke) exit 0 ;;
  full)
    for name in MOTRPAC_RAW_COUNTS_DIR MOTRPAC_DEA_DIR; do
      [[ -n "${!name:-}" && -d "${!name}" ]] || { echo "Set ${name} to an existing declared directory; see input_manifest.tsv" >&2; exit 1; }
    done
    for name in MOTRPAC_TRANSCRIPT_METADATA_TSV MOTRPAC_PHENOTYPE_METADATA_TSV MOTRPAC_FEATURE_TO_GENE_TSV MOTRPAC_RAT_TO_HUMAN_TSV MOTRPAC_FEATURE_ANNOT MOTRPAC_MAPPING_FILE; do
      [[ -n "${!name:-}" && -f "${!name}" ]] || { echo "Set ${name} to an existing declared input; see input_manifest.tsv" >&2; exit 1; }
    done
    ;;
  *) echo "usage: download_inputs.sh [--smoke|full]" >&2; exit 2 ;;
esac
