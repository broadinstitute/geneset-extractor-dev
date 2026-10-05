#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
out_root="${SUBMISSION_WORK_DIR:-${root}/outputs/direct_import}"
dig="${DIG_REPO:-$(cd -- "${root}/../.." && pwd -P)/dig-gene-set-extractors}"
for model_dir in "${out_root}"/genesets/*/models/*; do
  [[ -d "${model_dir}/extractor" ]] || continue
  model_id="$(basename "${model_dir}")"
  PYTHON_BIN="${PYTHON_BIN:-python3}" DIG_DIR="${dig}" bash "${root}/../run/refresh_model_metadata_and_provenance.sh" \
    --model_id "${model_id}" --model_dir "${model_dir}" \
    --description_template_tsv "${root}/config/model_description_templates.tsv"
done
