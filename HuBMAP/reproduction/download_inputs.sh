#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke) exit 0 ;;
  full)
    : "${HUBMAP_RAW_ASCTB_DIR:?Set HUBMAP_RAW_ASCTB_DIR to the released ASCT+B v2.2 directory}"
    : "${HUBMAP_HUMAN_GENE_INFO:?Set HUBMAP_HUMAN_GENE_INFO to the NCBI human_gene_info file}"
    [[ -d "${HUBMAP_RAW_ASCTB_DIR}" ]] || { echo "Missing HUBMAP_RAW_ASCTB_DIR: ${HUBMAP_RAW_ASCTB_DIR}" >&2; exit 1; }
    [[ -f "${HUBMAP_HUMAN_GENE_INFO}" ]] || { echo "Missing HUBMAP_HUMAN_GENE_INFO: ${HUBMAP_HUMAN_GENE_INFO}" >&2; exit 1; }
    ;;
  *) echo "usage: download_inputs.sh [--smoke|full]" >&2; exit 2 ;;
esac
