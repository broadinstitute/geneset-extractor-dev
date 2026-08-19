#!/usr/bin/env bash
set -euo pipefail

mode=${1:-full}
case "${mode}" in --smoke|full) ;; *) echo 'usage: reproduce.sh [--smoke|full]' >&2; exit 2;; esac
dig_src="../../dig-gene-set-extractors/src"
if [[ "${mode}" == "--smoke" ]]; then
  PYTHONPATH="${dig_src}${PYTHONPATH:+:${PYTHONPATH}}" bash run/submit_models.sh --analysis-set-id IGVFDS3405NGXF --inputs-root tests/fixtures --expression-tsv tests/fixtures/igvf_perturbseq_smoke.tsv --out-dir outputs/smoke/IGVFDS3405NGXF/models/PS1
  exit 0
fi
bash reproduction/download_inputs.sh full
while IFS=$'\t' read -r analysis_set_id dataset_id enabled; do
  [[ "${analysis_set_id}" == "analysis_set_id" ]] && continue
  [[ "${enabled}" == "true" ]] || continue
  PYTHONPATH="${dig_src}${PYTHONPATH:+:${PYTHONPATH}}" bash run/submit_models.sh --analysis-set-id "${analysis_set_id}" --inputs-root "${IGVF_INPUTS_ROOT}" --out-dir "outputs/genesets/${analysis_set_id}/models/PS1"
done < config/partition_list.tsv
