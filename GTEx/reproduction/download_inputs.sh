#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke) exit 0 ;;
  full) ;;
  *) echo "usage: download_inputs.sh [--smoke|full]" >&2; exit 2 ;;
esac

cat >&2 <<'EOF'
Full GTEx inputs are intentionally not downloaded by this script. Obtain the
declared GTEx Analysis V10 and V8 releases according to GTEx Portal terms, then set:
  GTEX_V10_COUNTS_GCT
  GTEX_V10_SAMPLE_ATTRIBUTES_TSV
  GTEX_V10_SUBJECT_PHENOTYPES_TSV
  GTEX_V8_COUNTS_GCT
  GTEX_V8_TPM_GCT
  GTEX_V8_SAMPLE_ATTRIBUTES_TSV
  GTEX_V8_SUBJECT_PHENOTYPES_TSV
  GTEX_V8_HUMAN_GENE_INFO
  GTEX_GTF
EOF

for variable in GTEX_V10_COUNTS_GCT GTEX_V10_SAMPLE_ATTRIBUTES_TSV GTEX_V10_SUBJECT_PHENOTYPES_TSV GTEX_V8_COUNTS_GCT GTEX_V8_TPM_GCT GTEX_V8_SAMPLE_ATTRIBUTES_TSV GTEX_V8_SUBJECT_PHENOTYPES_TSV GTEX_V8_HUMAN_GENE_INFO GTEX_GTF; do
  if [[ -z "${!variable:-}" || ! -f "${!variable}" ]]; then
    echo "missing required full input: ${variable}" >&2
    exit 1
  fi
done
