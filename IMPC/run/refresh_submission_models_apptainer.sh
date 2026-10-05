#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR" >&2; exit 1; }
exec bash "${root}/../run/refresh_model_metadata_and_provenance_apptainer.sh" --model_id HZ1 --model_dir "${SUBMISSION_WORK_DIR}/genesets/all_phenotypes/models/HZ1" --description_template_tsv "${root}/config/model_description_templates.tsv" "$@"
