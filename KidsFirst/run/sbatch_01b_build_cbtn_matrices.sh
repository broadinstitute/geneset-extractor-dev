#!/bin/bash
#SBATCH --job-name=CBTN_matrices
#SBATCH --output=KidsFirst/logs/cbtn_matrices_%j.out
#SBATCH --error=KidsFirst/logs/cbtn_matrices_%j.err
#SBATCH --time=08:00:00
#SBATCH --mem=64G
#SBATCH --cpus-per-task=8
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# Build per-diagnosis RSEM count matrices for CBTN brain tumor studies.
# Prerequisite: CBTN RSEM files must be downloaded first.
#   Check: ls KidsFirst_CBTN/outputs/rsem_files/ | wc -l   (should be ~1,937)
#   If not downloaded: bash KidsFirst_CBTN/run/submit_download_cbtn_rsem.sh
#
# This script does NOT run DE analysis — that comes after deciding which
# diagnoses to compare and reviewing natural DE sizes.
# DE analysis will be added to sbatch_01_de_only.sh or a separate script.
#
# Output: outputs/analysis/CBTN-{diagnosis}/rsem_counts.tsv
# Also extracts GTEx brain cortex counts if not already done.

source /programs/biogrids.shrc
export PYTHON_X=3.9.16
unset PYTHONPATH

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
CBTN_DIR="/path/to/your/cbtn/project"
SRC_DIR="${PROJECT_DIR}/KidsFirst/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"
GTEX_DIR="${PROJECT_DIR}/inputs/GTEx/v10"
GTEX_ATTRS="${GTEX_DIR}/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt"
WORKERS="${SLURM_CPUS_PER_TASK:-8}"

DIG_DIR="/path/to/dig-gene-set-extractors"
# prep scripts (build_rsem_matrix/extract_gtex_counts) are thin shims that delegate to the
# DIG-owned kidsfirst_prepare workflow, so they run under the DIG venv Python.
PYTHON_BIN="${DIG_DIR}/.venv/bin/python"
CBTN_RSEM_DIR="${CBTN_DIR}/outputs/rsem_files"
CBTN_MANIFEST="${CBTN_DIR}/config/cbtn_rsem_full_manifest.tsv"

mkdir -p "${PROJECT_DIR}/KidsFirst/logs" "${ANALYSIS_DIR}/gtex"

echo "======================================================"
echo " CBTN matrix building"
echo " RSEM dir: ${CBTN_RSEM_DIR}"
echo " Manifest: ${CBTN_MANIFEST}"
echo " Start: $(date)"
echo "======================================================"

# ── Pre-flight check ──────────────────────────────────────────────────────────
if [[ ! -d "$CBTN_RSEM_DIR" ]]; then
  echo "[ERROR] CBTN rsem_files directory not found: ${CBTN_RSEM_DIR}"
  echo "        Submit download first: bash KidsFirst_CBTN/run/submit_download_cbtn_rsem.sh"
  exit 1
fi

N_RSEM=$(find "$CBTN_RSEM_DIR" -name "*.rsem.genes.results.gz" -not -empty 2>/dev/null | wc -l)
echo "[CHECK] CBTN RSEM files found: ${N_RSEM} (expected ~1,937)"
if [[ "$N_RSEM" -lt 100 ]]; then
  echo "[ERROR] Too few RSEM files (${N_RSEM}) — download may be incomplete"
  echo "        Check: bash KidsFirst_CBTN/run/check_download_status.sh"
  exit 1
fi

if [[ ! -f "$CBTN_MANIFEST" ]]; then
  echo "[ERROR] Manifest not found: ${CBTN_MANIFEST}"; exit 1
fi

# ── Sanity check helper ───────────────────────────────────────────────────────
check_matrix() {
  local label="$1" f="$2"
  if [[ ! -f "$f" ]]; then echo "[ERROR] Missing: $f"; exit 1; fi
  local genes samples
  genes=$(tail -n +2 "$f" | wc -l)
  samples=$(head -1 "$f" | awk -F'\t' '{print NF-1}')
  echo "[CHECK] ${label}: ${genes} genes × ${samples} samples"
  if [[ "$genes" -lt 10000 ]]; then
    echo "[WARN]  ${label}: <10,000 genes — verify gene IDs"
  fi
  if [[ "$samples" -lt 5 ]]; then
    echo "[WARN]  ${label}: very few samples (${samples}) — check filter"
  fi
}

# ── CBTN diagnoses to build (n ≥ 60 in full manifest) ────────────────────────
# Format: "slug|label|expected_N"
DIAGNOSES=(
  "low_grade_glioma|Low Grade Glioma|408"
  "malignant_glioma|Malignant Glioma|278"
  "medulloblastoma|Medulloblastoma|213"
  "ependymoma|Ependymoma|176"
  "ganglioglioma|Ganglioglioma|75"
  "craniopharyngioma|Craniopharyngioma|74"
  "atypical_teratoid_rhabdoid_tumor|ATRT|60"
)

echo ""
echo "====== Building per-diagnosis RSEM matrices ======"
echo ""

for ENTRY in "${DIAGNOSES[@]}"; do
  IFS="|" read -r SLUG LABEL EXPECTED <<< "$ENTRY"
  OUT="${ANALYSIS_DIR}/CBTN-${SLUG}/rsem_counts.tsv"
  mkdir -p "${ANALYSIS_DIR}/CBTN-${SLUG}"

  if [[ -f "$OUT" ]]; then
    echo "[SKIP] CBTN-${SLUG} already exists"
    check_matrix "CBTN-${SLUG}" "$OUT"
    continue
  fi

  echo "[RUN] Building: CBTN-${SLUG} (expected ~${EXPECTED} samples)..."
  "${PYTHON_BIN}" "${SRC_DIR}/build_rsem_matrix.py" \
    --rsem_dir        "$CBTN_RSEM_DIR" \
    --manifest_tsv    "$CBTN_MANIFEST" \
    --out_tsv         "$OUT" \
    --workers         "${WORKERS}" \
    --filter_column   "diagnosis_slug" \
    --filter_value    "${SLUG}"

  check_matrix "CBTN-${SLUG}" "$OUT"

  # Verify expected sample count
  actual=$(head -1 "$OUT" | awk -F'\t' '{print NF-1}')
  if [[ "$actual" -lt 10 ]]; then
    echo "[WARN]  CBTN-${SLUG}: only ${actual} samples — diagnosis slug may not match manifest"
  fi
done

# ── GTEx brain cortex (normal reference for CBTN) ────────────────────────────
echo ""
echo "====== GTEx brain cortex (CBTN normal reference) ======"

GTEX_BRAIN="${ANALYSIS_DIR}/gtex/brain_cortex.tsv"
if [[ -f "$GTEX_BRAIN" ]]; then
  echo "[SKIP] GTEx brain_cortex already extracted"
  check_matrix "GTEx/brain_cortex" "$GTEX_BRAIN"
else
  echo "[RUN] Extracting GTEx Brain - Cortex..."
  "${PYTHON_BIN}" "${SRC_DIR}/extract_gtex_counts.py" \
    --gct          "${GTEX_DIR}/gene_reads_v10_brain_cortex.gct.gz" \
    --sample_attrs "${GTEX_ATTRS}" \
    --tissue       "Brain - Cortex" \
    --out_tsv      "$GTEX_BRAIN"
  check_matrix "GTEx/brain_cortex" "$GTEX_BRAIN"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "====== Summary: CBTN matrices built ======"
for ENTRY in "${DIAGNOSES[@]}"; do
  IFS="|" read -r SLUG LABEL EXPECTED <<< "$ENTRY"
  OUT="${ANALYSIS_DIR}/CBTN-${SLUG}/rsem_counts.tsv"
  if [[ -f "$OUT" ]]; then
    N=$(head -1 "$OUT" | awk -F'\t' '{print NF-1}')
    printf "  %-45s %s samples\n" "CBTN-${SLUG}" "${N}"
  else
    printf "  %-45s MISSING\n" "CBTN-${SLUG}"
  fi
done

echo ""
echo "======================================================"
echo " CBTN matrix building DONE: $(date)"
echo " Next: decide CBTN comparisons, add to sbatch_01_de_only.sh"
echo "======================================================"
