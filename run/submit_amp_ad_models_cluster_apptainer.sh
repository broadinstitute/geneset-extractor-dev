#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
APPTAINER_BIN="${APPTAINER_BIN:-apptainer}"
APPTAINER_IMAGE="${APPTAINER_IMAGE:-}"
APPTAINER_EXTRA_ARGS="${APPTAINER_EXTRA_ARGS:-}"

if [[ -z "${APPTAINER_IMAGE}" ]]; then
  echo "Missing required environment variable: APPTAINER_IMAGE" >&2
  exit 1
fi

exec "${APPTAINER_BIN}" exec ${APPTAINER_EXTRA_ARGS} \
  --bind "${REPO_ROOT}:${REPO_ROOT}" \
  "${APPTAINER_IMAGE}" \
  bash "${REPO_ROOT}/geneset-extractor-dev/run/submit_amp_ad_models_cluster.sh" "$@"
