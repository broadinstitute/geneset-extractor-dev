#!/usr/bin/env bash
set -euo pipefail
library_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
mkdir -p "${library_root}/inputs"
while IFS=$'\t' read -r input_id source_uri; do
  filename="${source_uri##*/}"
  dataset_id=$(awk -F $'\t' -v id="${input_id}" '$5 == id {print $1; exit}' "${library_root}/config/task_manifest.tsv")
  destination="${library_root}/inputs/${dataset_id}/${input_id}/${filename}"
  mkdir -p "$(dirname -- "${destination}")"
  if [[ -s "${destination}" ]]; then
    continue
  fi
  curl --fail --location --retry 2 --output "${destination}" "${source_uri}"
done < <(awk -F $'\t' 'NR > 1 && $6 ~ /(^|,)full(,|$)/ {print $1 "\t" $2}' "${library_root}/reproduction/input_manifest.tsv")
