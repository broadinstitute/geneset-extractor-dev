#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/generate_gtex_model_sweep_proposal.v1.py" \
  --output_dir "${repo_root}/outputs/gtex_model_sweep_v1" \
  "$@"
