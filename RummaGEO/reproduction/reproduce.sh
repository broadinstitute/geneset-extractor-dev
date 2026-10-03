#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
shift || true
case "${mode}" in --smoke|--full|full) ;; *) echo "usage: reproduce.sh [--smoke|--full|full]" >&2; exit 2 ;; esac
[[ "${mode}" == "--full" ]] && mode="full"
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
output_root="${SUBMISSION_WORK_DIR:-${root}/work}"
mkdir -p "${output_root}"
if [[ "${mode}" == "full" && "${RUMMAGEO_ORCHESTRATE_ALL:-0}" == "1" ]]; then
  : "${RUMMAGEO_HUMAN_GMT:?Set RUMMAGEO_HUMAN_GMT}"
  : "${RUMMAGEO_MOUSE_GMT:?Set RUMMAGEO_MOUSE_GMT}"
  : "${RUMMAGEO_HUMAN_GENE_INFO:?Set RUMMAGEO_HUMAN_GENE_INFO}"
  : "${RUMMAGEO_MOUSE_GENE_INFO:?Set RUMMAGEO_MOUSE_GENE_INFO}"
  : "${RUMMAGEO_GENE_ORTHOLOGS:?Set RUMMAGEO_GENE_ORTHOLOGS}"
  exec "${PYTHON_BIN:-python3}" -m geneset_extractors.cli convert rumma_geo_all \
    --human_gmt "${RUMMAGEO_HUMAN_GMT}" --mouse_gmt "${RUMMAGEO_MOUSE_GMT}" \
    --human_gene_info "${RUMMAGEO_HUMAN_GENE_INFO}" --mouse_gene_info "${RUMMAGEO_MOUSE_GENE_INFO}" \
    --gene_orthologs "${RUMMAGEO_GENE_ORTHOLOGS}" --out_dir "${output_root}" "$@"
fi
dispatch_mode="${mode}"
[[ "${dispatch_mode}" == "full" ]] && dispatch_mode="--full"
exec bash "${root}/run/run_submission_models.sh" "${dispatch_mode}" --out-root "${output_root}" "$@"
