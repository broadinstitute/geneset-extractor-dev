#!/usr/bin/env bash
set -euo pipefail
mode=${1:-full}
case "${mode}" in --smoke) inputs_root=tests/fixtures; out_root=outputs/smoke; extra=(--smoke) ;; full) inputs_root=${IGVF_INPUTS_ROOT:?Set IGVF_INPUTS_ROOT to the downloaded declared source inputs}; out_root=outputs/full; extra=() ;; *) echo 'usage: reproduce.sh [--smoke|full]' >&2; exit 2;; esac
exec python3 src/build_igvf_library.py --inputs_root "${inputs_root}" --out_root "${out_root}" "${extra[@]}"
