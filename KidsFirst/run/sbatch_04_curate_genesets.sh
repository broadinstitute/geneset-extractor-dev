#!/bin/bash
#SBATCH --job-name=KF_curate
#SBATCH --output=KidsFirst/logs/kf_curate_%j.out
#SBATCH --error=KidsFirst/logs/kf_curate_%j.err
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=2
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# ── Curated disease gene sets (KidsFirst + CBTN) ──────────────────────────────
# Prerequisites:
#   sbatch_01_de_only.sh   (KF: TALL, NBL, ESGR, MMC)
#   sbatch_02_cbtn_de.sh   (CBTN: 7 brain tumor diagnoses) — skipped if not complete
#
# Both KF and CBTN DE results land in the same ANALYSIS_DIR, so this script
# covers both automatically. Re-run after sbatch_02 completes to add CBTN sets.
#
# Strategy (disease_up.gmt = PRIMARY):
#   - Tumor-upregulated only (padj<0.05, logFC≥1, valid gene symbol)
#   - Multiple controls (KF_TALL) → intersection = concordant core
#   - Score threshold: mean signed_neglog10padj >= 2.0 (≈ padj<0.01) applied after concordance
#   - Fallback to score>=1.30 (padj<0.05) if result < 50
#   - Safety cap 200 (ceiling, not target); warn if final < 50
#
# Downregulated genes (tissue_markers_dn.gmt = QC ONLY):
#   - In tumor_vs_normal comparisons: reflects tissue/control identity, not disease
#   - Not for primary PIGEAN enrichment
#
# Outputs in: outputs/analysis/curated_genesets/
#   disease_up.gmt          PRIMARY: delivery disease gene sets
#   tissue_markers_dn.gmt   QC: normal-tissue markers (tumor vs normal down)
#   manifest.tsv            audit trail with concordance strategy per disease
# ─────────────────────────────────────────────────────────────────────────────

source /programs/biogrids.shrc
export PYTHON_X=3.9.16
unset PYTHONPATH

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
SRC_DIR="${PROJECT_DIR}/KidsFirst/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"
OUT_DIR="${ANALYSIS_DIR}/curated_genesets"

PYTHON_BIN="python3"

mkdir -p "${PROJECT_DIR}/KidsFirst/logs"
echo "======================================================"
echo " Curated disease gene set extraction (KF + CBTN)"
echo " padj<0.05 | logFC≥1 | concordant | score>=2.0 | cap=200 | warn<50"
echo " Start: $(date)"
echo "======================================================"

"${PYTHON_BIN}" "${SRC_DIR}/curate_disease_genesets.py" \
  --analysis_dir    "${ANALYSIS_DIR}" \
  --out_dir         "${OUT_DIR}" \
  --padj_max        0.05 \
  --min_logfc       1.0 \
  --score_threshold 2.0 \
  --safety_cap      200 \
  --min_genes       50 \
  --min_core        10

echo ""
echo "======================================================"
echo " Done: $(date)"
echo " Outputs: ${OUT_DIR}"
echo " Check manifest.tsv for warn_small flags (< 50 genes)"
echo "======================================================"
