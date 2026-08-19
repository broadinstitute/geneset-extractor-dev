#!/usr/bin/env bash
set -euo pipefail

mode=${1:-full}
[[ "${mode}" == "--smoke" ]] && exit 0
inputs_root=${IGVF_INPUTS_ROOT:?Set IGVF_INPUTS_ROOT to the untracked directory for released IGVF inputs.}
while IFS=$'\t' read -r analysis_set_id dataset_id file_relpath _; do
  [[ "${analysis_set_id}" == "analysis_set_id" ]] && continue
  destination="${inputs_root}/${file_relpath}"
  filename="${file_relpath##*/}"
  mkdir -p "$(dirname "${destination}")"
  if [[ ! -f "${destination}" ]]; then
    curl --fail --location --silent --show-error "https://api.data.igvf.org/tabular-files/${dataset_id}/@@download/${filename}" --output "${destination}"
  fi
done < config/analysis_set_list.tsv
