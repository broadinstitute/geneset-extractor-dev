#!/usr/bin/env bash
set -euo pipefail

library_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
inputs_root=${1:-"${library_root}/../../inputs/IGVF"}
config=${library_root}/config/analysis_set_list.tsv
portal=${IGVF_PORTAL:-https://api.data.igvf.org}

mkdir -p "${inputs_root}"
while IFS=$'\t' read -r analysis_set_id dataset_id file_relpath schema sep term_column gene_symbol_column gene_id_column effect_column ratio_column score_column pvalue_column pvalue_max score_threshold top_k_per_direction enabled; do
  [[ "${analysis_set_id}" == "analysis_set_id" || "${enabled}" != "true" ]] && continue
  destination=${inputs_root}/${file_relpath}
  mkdir -p "$(dirname -- "${destination}")"
  if [[ -s "${destination}" ]]; then
    echo "using existing ${destination}" >&2
    continue
  fi
  echo "downloading ${dataset_id} for ${analysis_set_id}" >&2
  curl --fail --silent --show-error --location \
    "${portal}/tabular-files/${dataset_id}/@@download/${file_relpath##*/}" \
    --output "${destination}"
done < "${config}"
