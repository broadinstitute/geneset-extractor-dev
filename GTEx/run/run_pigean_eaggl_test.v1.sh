#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_pigean_eaggl_test.v1.py" \
  --output_dir "${repo_root}/outputs/pigean_eaggl_test_v1" \
  --pigean_repo "${repo_root}/pigean" \
  --source_gmt_gz "${repo_root}/outputs/gtex_no_harmonizome_analysis_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz" \
  "$@"
