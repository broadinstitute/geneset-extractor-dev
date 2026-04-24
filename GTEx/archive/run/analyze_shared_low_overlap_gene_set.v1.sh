#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/analyze_shared_low_overlap_gene_set.v1.py" \
  --set_name "GTEx_Skin_20-29_vs_60-69_Up" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --reproduced_gmt_gz "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz" \
  --comparison_to_reference_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/comparison_to_reference.v1.tsv" \
  --deg_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/deg_long_combined.v1.tsv" \
  --comparison_manifest_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/comparison_manifest_all.v1.tsv" \
  --processed_matrix_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/tissue_matrices_processed/Skin.v1.tsv" \
  --output_dir "${repo_root}/outputs/shared_low_overlap_gene_set_analysis_v1" \
  "$@"
