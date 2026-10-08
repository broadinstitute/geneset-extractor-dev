#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec env PROVENANCE_OPERATION=deduplicate bash "${SCRIPT_DIR}/convert_provenance_apptainer.sh" "$@"
