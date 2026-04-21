#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/analyze_missing_legacy_set_representation.v1.py" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --generated_gmt_gz "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz" \
  --comparison_manifest_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/comparison_manifest_all.v1.tsv" \
  --sample_metadata_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/sample_metadata_all.v1.tsv" \
  --combined_deg_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/deg_long_combined.v1.tsv" \
  --output_dir "${repo_root}/outputs/harmonizome_missing_set_representation_v1" \
  "$@"
