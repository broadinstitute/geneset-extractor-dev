#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_harmonizome_recovery_sweep.v1.py" \
  --prepared_inputs_tsv "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1/prepared/prepared_tissue_inputs.v1.tsv" \
  --reference_gmt_gz "${repo_root}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz" \
  --output_dir "${repo_root}/outputs/harmonizome_recovery_sweep_v1" \
  "$@"
