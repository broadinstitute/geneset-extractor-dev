#!/usr/bin/env bash
set -euo pipefail
inputs_root=${1:-${IGVF_INPUTS_ROOT:-}}
if [[ -z "${inputs_root}" ]]; then
  echo 'usage: download_inputs.sh <destination>, or set IGVF_INPUTS_ROOT' >&2
  exit 2
fi
config_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../config" && pwd -P)
tail -n +2 "${config_dir}/analysis_set_list.tsv" | while IFS=$'\t' read -r analysis_set_id dataset_id file_relpath _; do
  destination="${inputs_root}/${file_relpath}"
  mkdir -p "$(dirname -- "${destination}")"
  if [[ -s "${destination}" ]]; then
    echo "existing ${destination}" >&2
    continue
  fi
  extension=${file_relpath##*.}
  curl --fail --silent --show-error --location \
    "https://api.data.igvf.org/tabular-files/${dataset_id}/@@download/${dataset_id}.${extension}" \
    -o "${destination}"
done
