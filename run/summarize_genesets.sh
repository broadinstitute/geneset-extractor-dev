#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
PYTHONPATH="${repo_root}${PYTHONPATH:+:${PYTHONPATH}}" python3 -m submission_tools.postrun_report "$@"
