#!/usr/bin/env bash
#
# Download ImmPort RNA-seq result files for one study (SDY accession).
#
# Wrapper-only acquisition logic (no gene-set logic). Uses the ImmPort REST API:
#   1. POST username/password to the auth endpoint to get a bearer token.
#   2. Query the filePath API for the study to build a file manifest.
#   3. Download each file via the data/download API, recording sources.tsv.
#
# Read the study's RNA_sequencing_result README first to learn the expression-matrix
# and sample/phenotype file names, then map them into ImmPort/config/study_list.tsv
# (expression_object, sample_metadata_object) and the per-study contrast columns.
#
# Credentials (free self-service registration at immport.org):
#   export IMMPORT_USERNAME=...
#   export IMMPORT_PASSWORD=...
#
# Usage:
#   IMMPORT_USERNAME=... IMMPORT_PASSWORD=... \
#     ./ImmPort/run/fetch_immport_inputs.sh <SDY_ACCESSION> [OUT_DIR]
#
# Example:
#   ./ImmPort/run/fetch_immport_inputs.sh SDY1299 inputs/ImmPort/SDY1299
#
set -euo pipefail

STUDY_ID="${1:-}"
OUT_DIR="${2:-inputs/ImmPort/${STUDY_ID}}"
IMMPORT_AUTH_URL="${IMMPORT_AUTH_URL:-https://auth.immport.org/auth/token}"
IMMPORT_API_URL="${IMMPORT_API_URL:-https://api.immport.org}"

if [[ -z "${STUDY_ID}" ]]; then
  echo "Usage: $0 <SDY_ACCESSION> [OUT_DIR]" >&2
  exit 1
fi
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }
: "${IMMPORT_USERNAME:?Set IMMPORT_USERNAME}"
: "${IMMPORT_PASSWORD:?Set IMMPORT_PASSWORD}"

echo "Authenticating to ImmPort ..." >&2
TOKEN="$(curl -fsSL -X POST "${IMMPORT_AUTH_URL}" \
  --data-urlencode "username=${IMMPORT_USERNAME}" \
  --data-urlencode "password=${IMMPORT_PASSWORD}" | jq -r '.token')"
if [[ -z "${TOKEN}" || "${TOKEN}" == "null" ]]; then
  echo "Failed to obtain ImmPort auth token" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
SOURCES_TSV="${OUT_DIR}/sources.tsv"
printf "local_path\tsource_url\tfile_path\n" > "${SOURCES_TSV}"

echo "Querying file manifest for ${STUDY_ID} (RNA sequencing results) ..." >&2
# filePath API returns rows describing each shared-data file for a study.
MANIFEST="$(curl -fsSL -H "Authorization: bearer ${TOKEN}" \
  "${IMMPORT_API_URL}/data/query/filePath?studyAccession=${STUDY_ID}")"

echo "${MANIFEST}" \
  | jq -r '.[] | select((.fileDetail // .filePath // "") | test("RNA_sequencing_result"; "i")) | (.filePath // .fileDetail)' \
  | while IFS= read -r file_path; do
      [[ -n "${file_path}" ]] || continue
      fname="$(basename "${file_path}")"
      dest="${OUT_DIR}/${fname}"
      url="${IMMPORT_API_URL}/data/download/file/${file_path}"
      echo "  downloading ${fname} ..." >&2
      curl -fsSL -H "Authorization: bearer ${TOKEN}" -o "${dest}" "${url}"
      printf "%s\t%s\t%s\n" "${dest}" "${url}" "${file_path}" >> "${SOURCES_TSV}"
    done

echo "Done. Files in ${OUT_DIR}; source map at ${SOURCES_TSV}" >&2
echo "Next: read the README, then set expression_object/sample_metadata_object and the" >&2
echo "      group_column/case_label/control_label/covariates for ${STUDY_ID} in ImmPort/config/study_list.tsv." >&2
