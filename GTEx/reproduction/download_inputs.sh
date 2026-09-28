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
declared GTEx Analysis V10 release according to GTEx Portal terms, then set:
  GTEX_COUNTS_GCT
  GTEX_SAMPLE_ATTRIBUTES_TSV
  GTEX_SUBJECT_PHENOTYPES_TSV
  GTEX_GTF
EOF

for variable in GTEX_COUNTS_GCT GTEX_SAMPLE_ATTRIBUTES_TSV GTEX_SUBJECT_PHENOTYPES_TSV GTEX_GTF; do
  if [[ -z "${!variable:-}" || ! -f "${!variable}" ]]; then
    echo "missing required full input: ${variable}" >&2
    exit 1
  fi
done
