#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
root=""; dig_dir="${DIG_REPO:-${repo_root}/dig-gene-set-extractors}"; chunk_size=25; progress_every=10000; memory=""; submit=0; references=(); overwrite=0
while [[ $# -gt 0 ]]; do case "$1" in
  --local-output-root) root="$2"; shift 2;; --dig-dir) dig_dir="$2"; shift 2;; --evaluation-reference) references+=("$2"); shift 2;;
  --chunk-size) chunk_size="$2"; shift 2;; --progress-every) progress_every="$2"; shift 2;; --memory) memory="$2"; shift 2;; --overwrite) overwrite=1; shift;; --submit) submit=1; shift;;
  -h|--help) echo "usage: $0 --local-output-root DIR --evaluation-reference PATH [--chunk-size N] [--progress-every N] [--memory SIZE] [--submit]"; exit 0;; *) echo "unknown argument: $1" >&2; exit 2;; esac; done
[[ -n "$root" && ${#references[@]} -gt 0 ]] || { echo "--local-output-root and --evaluation-reference are required" >&2; exit 2; }
python_bin="${PYTHON_BIN:-python3}"
if [[ "$python_bin" != /* ]]; then
  python_bin="$(command -v "$python_bin")" || { echo "Python interpreter not found: ${PYTHON_BIN:-python3}" >&2; exit 2; }
fi
[[ -x "$python_bin" ]] || { echo "Python interpreter is not executable: $python_bin" >&2; exit 2; }
work_dir="${root}/evaluation_tasks"; worklist="${work_dir}/worklist.tsv"; mkdir -p "${work_dir}/logs"
common=(--local-output-root "$root" --dig-dir "$dig_dir" --worklist "$worklist" --chunk-size "$chunk_size" --progress-every "$progress_every")
for reference in "${references[@]}"; do common+=(--reference "$reference"); done
[[ $overwrite -eq 1 ]] && common+=(--overwrite)
result="$("$python_bin" "${repo_root}/geneset-extractor-dev/src/evaluate_gmt_chunks.py" "${common[@]}" | tee /dev/stderr)"
[[ $submit -eq 1 ]] || exit 0
chunks="${result##*chunks=}"; [[ "$chunks" -gt 0 ]] || exit 0
qsub_args=(-b y -N geneset_evaluation -o "${work_dir}/logs" -e "${work_dir}/logs" -t "1-${chunks}" -v "PYTHON_BIN=${python_bin}")
[[ -n "$memory" ]] && qsub_args+=(-l "h_vmem=${memory}")
exec "${QSUB_BIN:-qsub}" "${qsub_args[@]}" bash "${script_dir}/run_evaluation_chunk.sh" "${common[@]}"
