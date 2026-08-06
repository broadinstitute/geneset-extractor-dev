#!/usr/bin/env bash
set -euo pipefail

mode="${1:---smoke}"
case "${mode}" in
  --smoke|full) ;;
  *) echo "usage: reproduce.sh [--smoke|full]" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "${root}/reproduction/download_inputs.sh"
python3 "${root}/src/simulate_dig_entrypoint.py" "--mode=${mode}" --input "${root}/tests/fixtures/tiny_input.tsv"
