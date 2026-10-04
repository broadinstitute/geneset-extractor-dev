#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke)
    exit 0
    ;;
  --full|full)
    : "${RUMMAGEO_HUMAN_GMT:?Set RUMMAGEO_HUMAN_GMT}"
    : "${RUMMAGEO_MOUSE_GMT:?Set RUMMAGEO_MOUSE_GMT}"
    : "${RUMMAGEO_HUMAN_GENE_INFO:?Set RUMMAGEO_HUMAN_GENE_INFO}"
    : "${RUMMAGEO_MOUSE_GENE_INFO:?Set RUMMAGEO_MOUSE_GENE_INFO}"
    : "${RUMMAGEO_GENE_ORTHOLOGS:?Set RUMMAGEO_GENE_ORTHOLOGS}"
    for input_path in "${RUMMAGEO_HUMAN_GMT}" "${RUMMAGEO_MOUSE_GMT}" "${RUMMAGEO_HUMAN_GENE_INFO}" "${RUMMAGEO_MOUSE_GENE_INFO}" "${RUMMAGEO_GENE_ORTHOLOGS}"; do
      [[ -f "${input_path}" ]] || { echo "Missing RummaGEO input: ${input_path}" >&2; exit 1; }
    done
    ;;
  *)
    echo "usage: download_inputs.sh [--smoke|--full]" >&2
    exit 2
    ;;
esac
