#!/usr/bin/env bash
# refresh_all_v3_libraries.sh
#
# Submits provenance-repair qsub arrays for all four v3 libraries:
#   GTEx, MoTrPAC, HuBMAP, LINCS_L1000
#
# Each library's submit script is called with --submit --refresh_metadata_and_provenance,
# which fans out one qsub job per model and runs refresh_model_metadata_and_provenance.py
# on each model directory.
#
# Usage:
#   Edit the CONFIG section below, then run on the cluster:
#     bash run/refresh_all_v3_libraries.sh [--gtex|--motrpac|--hubmap|--lincs|--all]
#
# Default (no flag): submits all four libraries.
#
# Prerequisites:
#   dig-gene-set-extractors branch cfde-geneset-deliverables
#   geneset-extractor-dev   branch (this repo)
#   PYBIN points to the conda env with geneset_extractors installed
#   qsub available on the PATH

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG — fill in before running
# ──────────────────────────────────────────────────────────────────────────────

PYBIN="${PYBIN:-/home/unix/gage/.conda/envs/gsx310/bin/python}"
DIG_DIR="${DIG_DIR:-/humgen/diabetes2/users/gage/software/dig-gene-set-extractors}"

# Cluster output roots — where each library's all_models dir lives.
# Pattern from scRNA_cNMF v4: /humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions/gage/v4/scRNA_cNMF/scrna_cnmf_all_models
GTEX_OUT_ROOT="${GTEX_OUT_ROOT:-/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions/gage/v3/GTEx/gtex_all_models}"
MOTRPAC_OUT_ROOT="${MOTRPAC_OUT_ROOT:-/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions/gage/v3/MoTrPAC/motrpac_all_models}"
HUBMAP_OUT_ROOT="${HUBMAP_OUT_ROOT:-/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions/gage/v3/HuBMAP/hubmap_all_models}"
LINCS_OUT_ROOT="${LINCS_OUT_ROOT:-/humgen/diabetes2/users/ryank/CFDE/geneset_extractors/submissions/gage/v3/LINCS_L1000/lincs_l1000_all_models}"

# Description template TSVs (ship with the repo under <Library>/config/)
GTEX_DESC_TEMPLATE="${GTEX_DESC_TEMPLATE:-${REPO_ROOT}/geneset-extractor-dev/GTEx/config/model_description_templates.tsv}"
MOTRPAC_DESC_TEMPLATE="${MOTRPAC_DESC_TEMPLATE:-${REPO_ROOT}/geneset-extractor-dev/MoTrPAC/config/model_description_templates.tsv}"
HUBMAP_DESC_TEMPLATE="${HUBMAP_DESC_TEMPLATE:-${REPO_ROOT}/geneset-extractor-dev/HuBMAP/config/model_description_templates.tsv}"
LINCS_DESC_TEMPLATE="${LINCS_DESC_TEMPLATE:-${REPO_ROOT}/geneset-extractor-dev/LINCS_L1000/config/model_description_templates.tsv}"

# Provenance mirror: rewrites cluster-local output paths to public cfde:// URIs.
# LOCAL_PREFIX = the cluster output root (same as *_OUT_ROOT above).
# REMOTE_PREFIX = the cfde:// URI root that replaces it in provenance files.
# Leave both empty to skip path rewriting (outputs will retain cluster paths).
GTEX_PROVENANCE_MIRROR_LOCAL="${GTEX_PROVENANCE_MIRROR_LOCAL:-${GTEX_OUT_ROOT}}"
GTEX_PROVENANCE_MIRROR_REMOTE="${GTEX_PROVENANCE_MIRROR_REMOTE:-cfde://GTEx}"

MOTRPAC_PROVENANCE_MIRROR_LOCAL="${MOTRPAC_PROVENANCE_MIRROR_LOCAL:-${MOTRPAC_OUT_ROOT}}"
MOTRPAC_PROVENANCE_MIRROR_REMOTE="${MOTRPAC_PROVENANCE_MIRROR_REMOTE:-cfde://MoTrPAC}"

HUBMAP_PROVENANCE_MIRROR_LOCAL="${HUBMAP_PROVENANCE_MIRROR_LOCAL:-${HUBMAP_OUT_ROOT}}"
HUBMAP_PROVENANCE_MIRROR_REMOTE="${HUBMAP_PROVENANCE_MIRROR_REMOTE:-cfde://HuBMAP}"

LINCS_PROVENANCE_MIRROR_LOCAL="${LINCS_PROVENANCE_MIRROR_LOCAL:-${LINCS_OUT_ROOT}}"
LINCS_PROVENANCE_MIRROR_REMOTE="${LINCS_PROVENANCE_MIRROR_REMOTE:-cfde://LINCS_L1000}"

# Optional: TSV mapping local input file paths to public URLs, one per library.
# Columns: local_path<TAB>public_url
# Leave empty to skip input-path rewriting (input paths will stay as-is).
GTEX_LOCAL_INPUT_SOURCE_MAP="${GTEX_LOCAL_INPUT_SOURCE_MAP:-}"
MOTRPAC_LOCAL_INPUT_SOURCE_MAP="${MOTRPAC_LOCAL_INPUT_SOURCE_MAP:-}"
HUBMAP_LOCAL_INPUT_SOURCE_MAP="${HUBMAP_LOCAL_INPUT_SOURCE_MAP:-}"
LINCS_LOCAL_INPUT_SOURCE_MAP="${LINCS_LOCAL_INPUT_SOURCE_MAP:-}"

# qsub log root (per-library subdirs are created automatically)
QSUB_LOG_ROOT="${QSUB_LOG_ROOT:-${REPO_ROOT}/qsub_logs_v3_refresh}"

# ──────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ──────────────────────────────────────────────────────────────────────────────

RUN_GTEX=0
RUN_MOTRPAC=0
RUN_HUBMAP=0
RUN_LINCS=0

if [[ $# -eq 0 ]]; then
    RUN_GTEX=1; RUN_MOTRPAC=1; RUN_HUBMAP=1; RUN_LINCS=1
else
    for arg in "$@"; do
        case "$arg" in
            --gtex)    RUN_GTEX=1 ;;
            --motrpac) RUN_MOTRPAC=1 ;;
            --hubmap)  RUN_HUBMAP=1 ;;
            --lincs)   RUN_LINCS=1 ;;
            --all)     RUN_GTEX=1; RUN_MOTRPAC=1; RUN_HUBMAP=1; RUN_LINCS=1 ;;
            *) echo "Unknown flag: $arg" >&2; exit 1 ;;
        esac
    done
fi

# ──────────────────────────────────────────────────────────────────────────────
# GTEx
# ──────────────────────────────────────────────────────────────────────────────

if [[ ${RUN_GTEX} -eq 1 ]]; then
    echo "=== Submitting GTEx refresh ==="
    PYTHON_BIN="${PYBIN}" \
    DIG_DIR="${DIG_DIR}" \
    GTEX_OUT_ROOT="${GTEX_OUT_ROOT}" \
    QSUB_LOG_ROOT="${QSUB_LOG_ROOT}/gtex" \
    DESCRIPTION_TEMPLATE_TSV="${GTEX_DESC_TEMPLATE}" \
    PROVENANCE_MIRROR_LOCAL_PREFIX="${GTEX_PROVENANCE_MIRROR_LOCAL}" \
    PROVENANCE_MIRROR_REMOTE_PREFIX="${GTEX_PROVENANCE_MIRROR_REMOTE}" \
    LOCAL_INPUT_SOURCE_MAP_TSV="${GTEX_LOCAL_INPUT_SOURCE_MAP}" \
    bash "${REPO_ROOT}/geneset-extractor-dev/run/submit_gtex_models_cluster.sh" \
        --submit \
        --refresh_metadata_and_provenance
    echo "GTEx refresh submitted."
fi

# ──────────────────────────────────────────────────────────────────────────────
# MoTrPAC
# ──────────────────────────────────────────────────────────────────────────────

if [[ ${RUN_MOTRPAC} -eq 1 ]]; then
    echo ""
    echo "=== Submitting MoTrPAC refresh ==="
    PYTHON_BIN="${PYBIN}" \
    DIG_DIR="${DIG_DIR}" \
    MOTRPAC_OUT_ROOT="${MOTRPAC_OUT_ROOT}" \
    QSUB_LOG_ROOT="${QSUB_LOG_ROOT}/motrpac" \
    DESCRIPTION_TEMPLATE_TSV="${MOTRPAC_DESC_TEMPLATE}" \
    PROVENANCE_MIRROR_LOCAL_PREFIX="${MOTRPAC_PROVENANCE_MIRROR_LOCAL}" \
    PROVENANCE_MIRROR_REMOTE_PREFIX="${MOTRPAC_PROVENANCE_MIRROR_REMOTE}" \
    LOCAL_INPUT_SOURCE_MAP_TSV="${MOTRPAC_LOCAL_INPUT_SOURCE_MAP}" \
    bash "${REPO_ROOT}/geneset-extractor-dev/run/submit_motrpac_models_cluster.sh" \
        --submit \
        --refresh_metadata_and_provenance
    echo "MoTrPAC refresh submitted."
fi

# ──────────────────────────────────────────────────────────────────────────────
# HuBMAP
# ──────────────────────────────────────────────────────────────────────────────

if [[ ${RUN_HUBMAP} -eq 1 ]]; then
    echo ""
    echo "=== Submitting HuBMAP refresh ==="
    PYTHON_BIN="${PYBIN}" \
    DIG_DIR="${DIG_DIR}" \
    HUBMAP_OUT_ROOT="${HUBMAP_OUT_ROOT}" \
    QSUB_LOG_ROOT="${QSUB_LOG_ROOT}/hubmap" \
    DESCRIPTION_TEMPLATE_TSV="${HUBMAP_DESC_TEMPLATE}" \
    PROVENANCE_MIRROR_LOCAL_PREFIX="${HUBMAP_PROVENANCE_MIRROR_LOCAL}" \
    PROVENANCE_MIRROR_REMOTE_PREFIX="${HUBMAP_PROVENANCE_MIRROR_REMOTE}" \
    LOCAL_INPUT_SOURCE_MAP_TSV="${HUBMAP_LOCAL_INPUT_SOURCE_MAP}" \
    bash "${REPO_ROOT}/geneset-extractor-dev/run/submit_hubmap_models_cluster.sh" \
        --submit \
        --refresh_metadata_and_provenance
    echo "HuBMAP refresh submitted."
fi

# ──────────────────────────────────────────────────────────────────────────────
# LINCS_L1000
# ──────────────────────────────────────────────────────────────────────────────

if [[ ${RUN_LINCS} -eq 1 ]]; then
    echo ""
    echo "=== Submitting LINCS_L1000 refresh ==="
    PYTHON_BIN="${PYBIN}" \
    DIG_DIR="${DIG_DIR}" \
    LINCS_OUT_ROOT="${LINCS_OUT_ROOT}" \
    QSUB_LOG_ROOT="${QSUB_LOG_ROOT}/lincs_l1000" \
    DESCRIPTION_TEMPLATE_TSV="${LINCS_DESC_TEMPLATE}" \
    PROVENANCE_MIRROR_LOCAL_PREFIX="${LINCS_PROVENANCE_MIRROR_LOCAL}" \
    PROVENANCE_MIRROR_REMOTE_PREFIX="${LINCS_PROVENANCE_MIRROR_REMOTE}" \
    LOCAL_INPUT_SOURCE_MAP_TSV="${LINCS_LOCAL_INPUT_SOURCE_MAP}" \
    bash "${REPO_ROOT}/geneset-extractor-dev/run/submit_lincs_l1000_models_cluster.sh" \
        --submit \
        --refresh_metadata_and_provenance
    echo "LINCS_L1000 refresh submitted."
fi

echo ""
echo "Done. Monitor with: qstat -u \${USER}"
