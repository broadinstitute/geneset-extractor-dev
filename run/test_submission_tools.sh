#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"
PYTHONPATH="${repo_root}" python3 -m unittest -v tests.test_submission_tools

fixture_dir="$(mktemp -d)"
trap 'rm -rf "${fixture_dir}"' EXIT
PYTHONPATH="${repo_root}" python3 -m submission_tools scaffold --library-id ExampleSubmission --display-name "Example Submission" --pattern generic --output "${fixture_dir}/ExampleSubmission"
PYTHONPATH="${repo_root}" python3 -m submission_tools validate --submission "${fixture_dir}/ExampleSubmission"
