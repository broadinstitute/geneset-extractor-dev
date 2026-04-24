#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_pigean_eaggl_test.v3.py" \
  --output_dir "${repo_root}/outputs/pigean_eaggl_test_v3" \
  --pigean_repo "${repo_root}/pigean" \
  "$@"
