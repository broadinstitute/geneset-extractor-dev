#!/usr/bin/env bash
#
# Download IGVF processed perturbation-signature inputs for one analysis set.
#
# This is wrapper-only acquisition logic (no gene-set logic). It pulls files for an
# IGVF analysis set from the public REST API and records a sources.tsv mapping each
# local file to its canonical IGVF URL, so provenance refresh can point at the true
# external inputs (see run/refresh_model_metadata_and_provenance.sh --local_input_source_map_tsv).
#
# Credentials (released IGVF data is open, but bulk/API access uses an access key):
#   export IGVF_ACCESS_KEY=...      # from data.igvf.org -> User Profile -> Create Access Key
#   export IGVF_SECRET_KEY=...
#
# Usage:
#   IGVF_ACCESS_KEY=... IGVF_SECRET_KEY=... \
#     ./IGVF/run/fetch_igvf_inputs.sh <ANALYSIS_SET_ID> [OUT_DIR]
#
# Example:
#   ./IGVF/run/fetch_igvf_inputs.sh IGVFDS2266YDVM inputs/IGVF/IGVFDS2266YDVM
#
set -euo pipefail

ANALYSIS_SET_ID="${1:-}"
OUT_DIR="${2:-inputs/IGVF/${ANALYSIS_SET_ID}}"
IGVF_PORTAL="${IGVF_PORTAL:-https://api.data.igvf.org}"

if [[ -z "${ANALYSIS_SET_ID}" ]]; then
  echo "Usage: $0 <ANALYSIS_SET_ID> [OUT_DIR]" >&2
  exit 1
fi
command -v curl >/dev/null || { echo "curl is required" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

AUTH_ARGS=()
if [[ -n "${IGVF_ACCESS_KEY:-}" && -n "${IGVF_SECRET_KEY:-}" ]]; then
  AUTH_ARGS=(--user "${IGVF_ACCESS_KEY}:${IGVF_SECRET_KEY}")
else
  echo "WARNING: IGVF_ACCESS_KEY/IGVF_SECRET_KEY not set; only released open data will be reachable." >&2
fi

mkdir -p "${OUT_DIR}"
SOURCES_TSV="${OUT_DIR}/sources.tsv"
printf "local_path\tsource_url\taccession\tmd5sum\n" > "${SOURCES_TSV}"

echo "Querying analysis set ${ANALYSIS_SET_ID} ..." >&2
SET_JSON="$(curl -fsSL -H "Accept: application/json" "${AUTH_ARGS[@]}" \
  "${IGVF_PORTAL}/analysis-sets/${ANALYSIS_SET_ID}/?frame=embedded")"

# Each embedded file object exposes href, accession, md5sum, content_type/file_format.
echo "${SET_JSON}" | jq -r '
  (.files // [])[]
  | [ (.href // ""), (.accession // ""), (.md5sum // ""), (.file_format // .content_type // "") ]
  | @tsv
' | while IFS=$'\t' read -r href accession md5 fmt; do
  [[ -n "${href}" ]] || continue
  url="${IGVF_PORTAL}${href}"
  fname="${accession:-$(basename "${href}")}"
  [[ -n "${fmt}" ]] && fname="${fname}.${fmt}"
  dest="${OUT_DIR}/${fname}"
  echo "  downloading ${accession:-${fname}} ..." >&2
  curl -fsSL "${AUTH_ARGS[@]}" -o "${dest}" "${url}"
  printf "%s\t%s\t%s\t%s\n" "${dest}" "${url}" "${accession}" "${md5}" >> "${SOURCES_TSV}"
done

echo "Done. Files in ${OUT_DIR}; source map at ${SOURCES_TSV}" >&2
echo "Next: identify the processed per-perturbation signature matrix among the downloads and pass it as" >&2
echo "      IGVF_EXPRESSION_TSV (and optional IGVF_MAPPING_FILE) to the build/submit scripts." >&2
