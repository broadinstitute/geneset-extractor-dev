#!/usr/bin/env bash
set -euo pipefail
root="${GTEX_WRAPPER_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)}"
[[ -d "${root}" ]] || { echo "GTEX_WRAPPER_ROOT is not a GTEx wrapper directory: ${root}" >&2; exit 1; }
mode="${1:-full}"
[[ "${mode}" == "full" ]] || { echo "usage: run_hz2_task_apptainer.sh full" >&2; exit 2; }
[[ -n "${SUBMISSION_WORK_DIR:-}" ]] || { echo "Set SUBMISSION_WORK_DIR outside the GTEx checkout" >&2; exit 1; }
[[ -n "${DIG_REPO:-}" && -d "${DIG_REPO}" ]] || { echo "Set DIG_REPO to a DIG checkout" >&2; exit 1; }
[[ -n "${GTEX_V8_TPM_GCT:-}" && -f "${GTEX_V8_TPM_GCT}" ]] || { echo "Set GTEX_V8_TPM_GCT to the V8 TPM GCT" >&2; exit 1; }
for variable in GTEX_V8_SAMPLE_ATTRIBUTES_TSV GTEX_V8_SUBJECT_PHENOTYPES_TSV; do
  [[ -n "${!variable:-}" && -f "${!variable}" ]] || { echo "Set ${variable}" >&2; exit 1; }
done
if [[ -n "${GENESET_EXTRACTORS_IN_APPTAINER:-}" ]]; then
  exec bash "${root}/run/build_gtex_genesets.sh" full --task-id gtex_hz2_all_detailed_tissues --out-root "${SUBMISSION_WORK_DIR}"
fi
[[ -n "${APPTAINER_IMAGE:-}" && -f "${APPTAINER_IMAGE}" ]] || { echo "Set APPTAINER_IMAGE" >&2; exit 1; }
apptainer_bin="${APPTAINER_BIN:-apptainer}"
bind_paths=("$(cd -- "${root}/../.." && pwd -P)" "$(cd -- "${DIG_REPO}" && pwd -P)" "$(cd -- "${SUBMISSION_WORK_DIR}" && pwd -P)" "$(cd -- "$(dirname -- "${GTEX_V8_TPM_GCT}")" && pwd -P)" "$(cd -- "$(dirname -- "${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}")" && pwd -P)" "$(cd -- "$(dirname -- "${GTEX_V8_SUBJECT_PHENOTYPES_TSV}")" && pwd -P)")
bind_csv="$(printf '%s\n' "${bind_paths[@]}" | sort -u | paste -sd, -)"
APPTAINERENV_GENESET_EXTRACTORS_IN_APPTAINER=1 APPTAINERENV_SUBMISSION_WORK_DIR="${SUBMISSION_WORK_DIR}" APPTAINERENV_DIG_REPO="${DIG_REPO}" APPTAINERENV_GTEX_V8_TPM_GCT="${GTEX_V8_TPM_GCT}" APPTAINERENV_GTEX_V8_SAMPLE_ATTRIBUTES_TSV="${GTEX_V8_SAMPLE_ATTRIBUTES_TSV}" APPTAINERENV_GTEX_V8_SUBJECT_PHENOTYPES_TSV="${GTEX_V8_SUBJECT_PHENOTYPES_TSV}" exec "${apptainer_bin}" exec --bind "${bind_csv}" "${APPTAINER_IMAGE}" bash "${root}/run/run_hz2_task_apptainer.sh" full
