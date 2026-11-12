#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
root=""; dig_dir="${DIG_REPO:-${repo_root}/dig-gene-set-extractors}"; chunk_size=25; submit=0; references=(); overwrite=0
while [[ $# -gt 0 ]]; do case "$1" in
  --local-output-root) root="$2"; shift 2;; --dig-dir) dig_dir="$2"; shift 2;; --evaluation-reference) references+=("$2"); shift 2;;
  --chunk-size) chunk_size="$2"; shift 2;; --overwrite) overwrite=1; shift;; --submit) submit=1; shift;;
  -h|--help) echo "usage: $0 --local-output-root DIR --evaluation-reference PATH [--chunk-size N] [--submit]"; exit 0;; *) echo "unknown argument: $1" >&2; exit 2;; esac; done
[[ -n "$root" && ${#references[@]} -gt 0 ]] || { echo "--local-output-root and --evaluation-reference are required" >&2; exit 2; }
work_dir="${root}/evaluation_tasks"; worklist="${work_dir}/worklist.tsv"; mkdir -p "${work_dir}/logs"
common=(--local-output-root "$root" --dig-dir "$dig_dir" --worklist "$worklist" --chunk-size "$chunk_size")
for reference in "${references[@]}"; do common+=(--reference "$reference"); done
[[ $overwrite -eq 1 ]] && common+=(--overwrite)
result="$("${PYTHON_BIN:-python3}" "${repo_root}/geneset-extractor-dev/src/evaluate_gmt_chunks.py" "${common[@]}")"; echo "$result"
[[ $submit -eq 1 ]] || exit 0
chunks="${result##*chunks=}"; [[ "$chunks" -gt 0 ]] || exit 0
exec "${QSUB_BIN:-qsub}" -N geneset_evaluation -o "${work_dir}/logs" -e "${work_dir}/logs" -t "1-${chunks}" bash "${script_dir}/run_evaluation_chunk.sh" "${common[@]}"
