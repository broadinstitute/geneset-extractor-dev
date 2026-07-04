#!/usr/bin/env bash
# Run interactively on login node AFTER sbatch_01_de_only.sh completes.
# Reads all deg_long.tsv files and shows gene counts at multiple thresholds.
#
# Usage:
#   bash KidsFirst/run/02_check_natural_sizes.sh
#   bash KidsFirst/run/02_check_natural_sizes.sh --full   # verbose tables
#
# After reviewing output:
#   1. Edit TOP_K and MIN_LOGFC in sbatch_03_extract_genesets.sh
#   2. sbatch KidsFirst/run/sbatch_03_extract_genesets.sh

source /programs/biogrids.shrc
export PYTHON_X=3.9.16

PROJECT_DIR="/path/to/your/project"
SRC_DIR="${PROJECT_DIR}/KidsFirst/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"
PYTHON_BIN="python3"

FULL_MODE=false
[[ "${1:-}" == "--full" ]] && FULL_MODE=true

COMPARISONS=(
  "KF-TALL-vs-T21"
  "KF-TALL-vs-GTEx"
  "KF-NBL-vs-adrenal"
  "KF-ESGR-vs-muscle"
  "KF-MMC-vs-blood"
  "KF-TALL-vs-MMC"
  "KF-BLOOD-vs-normal"
  "KF-BLOOD-vs-SOLID"
)

echo "================================================================"
echo " Natural gene set size survey"
echo " Columns: |logFC| threshold → N_up↑ N_down↓"
echo " Goal: decide TOP_K and MIN_LOGFC for sbatch_03_extract_genesets.sh"
echo "================================================================"
echo ""

if $FULL_MODE; then
  # Full table per study
  for COMP in "${COMPARISONS[@]}"; do
    DEG="${ANALYSIS_DIR}/${COMP}/de_results/deg_long.tsv"
    "${PYTHON_BIN}" "${SRC_DIR}/summarize_de_natural_sizes.py" --deg_tsv "$DEG"
  done
else
  # Compact one-liner per study
  echo "Study                           |FC|≥0.5         |FC|≥1.0         |FC|≥1.5         |FC|≥2.0         |FC|≥2.5"
  echo "────────────────────────────────────────────────────────────────────────────────────────────────────────────────"
  for COMP in "${COMPARISONS[@]}"; do
    DEG="${ANALYSIS_DIR}/${COMP}/de_results/deg_long.tsv"
    if [[ ! -f "$DEG" ]]; then
      printf "%-30s  MISSING — run sbatch_01_de_only.sh first\n" "${COMP}"
      continue
    fi
    "${PYTHON_BIN}" "${SRC_DIR}/summarize_de_natural_sizes.py" \
      --deg_tsv "$DEG" --one_line
  done
fi

echo ""
echo "================================================================"
echo " How to read this:"
echo "   If |logFC|≥1 gives ≤150 genes → no top_k cap needed, use natural"
echo "   If |logFC|≥1 gives 200-500    → top_k=100 or 200 reasonable"
echo "   If |logFC|≥1 gives >500       → consider |logFC|≥1.5 or 2.0"
echo "   PIGEAN minimum: ≥50 genes per gene set"
echo ""
echo " Next steps:"
echo "   1. Edit TOP_K and MIN_LOGFC at the top of:"
echo "      KidsFirst/run/sbatch_03_extract_genesets.sh"
echo "   2. sbatch KidsFirst/run/sbatch_03_extract_genesets.sh"
echo ""
echo " For full per-study tables:"
echo "   bash KidsFirst/run/02_check_natural_sizes.sh --full"
echo "================================================================"
