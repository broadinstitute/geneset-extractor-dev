#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE to an existing image" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the HuBMAP checkout" >&2; exit 1; }
binds="${root},${DIG_REPO},${SUBMISSION_WORK_DIR}"
[[ -n "${HUBMAP_RAW_ASCTB_DIR:-}" ]] && binds+=",${HUBMAP_RAW_ASCTB_DIR}"
[[ -n "${HUBMAP_HUMAN_GENE_INFO:-}" ]] && binds+=",$(dirname "${HUBMAP_HUMAN_GENE_INFO}")"
exec "${APPTAINER_BIN:-apptainer}" exec --bind "${binds}" "${APPTAINER_IMAGE}" \
  env DIG_REPO="${DIG_REPO}" SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" \
  HUBMAP_RAW_ASCTB_DIR="${HUBMAP_RAW_ASCTB_DIR:-}" HUBMAP_HUMAN_GENE_INFO="${HUBMAP_HUMAN_GENE_INFO:-}" \
  bash "${root}/reproduction/reproduce.sh" "$@"
