#!/usr/bin/env bash
# Shared compatibility entrypoint for library-specific submission launchers.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
library=""

usage() {
  cat <<'EOF'
Usage: submit_submission_models_cluster_apptainer.sh --library LIBRARY [library launcher arguments]

Supported libraries: GTEx, HuBMAP, MoTrPAC, LINCS_L1000, GlyGen, IDG, IMPC,
GaultonLab, RummaGEO, MetabolomicsWorkbench.

All remaining arguments are forwarded unchanged to the library's established
launcher. This preserves its documented environment variables, scheduler
settings, model filters, and container behavior.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --library)
      [[ $# -ge 2 ]] || { echo "Missing value for --library" >&2; exit 2; }
      library="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) break ;;
  esac
done

[[ -n "$library" ]] || { echo "--library is required" >&2; usage >&2; exit 2; }
case "$library" in
  GTEx|HuBMAP|MoTrPAC|LINCS_L1000|GlyGen|IDG|IMPC|GaultonLab|RummaGEO|MetabolomicsWorkbench) ;;
  *) echo "Unsupported library: $library" >&2; exit 2 ;;
esac

launcher="${repo_root}/geneset-extractor-dev/${library}/run/submit_submission_models_cluster_apptainer.sh"
[[ -x "$launcher" ]] || { echo "Library launcher is not available: $launcher" >&2; exit 1; }
exec bash "$launcher" "$@"
