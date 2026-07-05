#!/bin/bash
#SBATCH --job-name=KF_genesets
#SBATCH --output=KidsFirst/logs/kf_genesets_%j.out
#SBATCH --error=KidsFirst/logs/kf_genesets_%j.err
#SBATCH --time=04:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=4
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# ── PHASE 2 of 2-phase workflow ───────────────────────────────────────────────
# Prerequisites:
#   sbatch_01_de_only.sh   (KF 6 delivered comparisons)
#   sbatch_02_cbtn_de.sh   (CBTN 7 comparisons) — skipped gracefully if not done
#
# Extracts the HZ1 harmonizome-style gene sets (padj<PADJ_MAX, |logFC|≥MIN_LOGFC,
# top_k=TOP_K) for the 13 delivered comparisons via the DIG rna_deg_multi converter.
# ─────────────────────────────────────────────────────────────────────────────

source /programs/biogrids.shrc
export PYTHON_X=3.9.16
unset PYTHONPATH

set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
TOP_K=100          # Cap for curated gene sets (genesets_topk/)
MIN_LOGFC="1.0"    # |log2FC| threshold
PADJ_MAX="0.05"    # FDR threshold
# GTF for gene symbol annotation (GENCODE v39, hg38 — matches GTEx v10 quantification).
# Download: https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_39/gencode.v39.annotation.gtf.gz
# Set to "" to skip annotation (gene_symbol will fall back to Ensembl IDs).
GTF_PATH=""        # e.g. /path/to/gencode.v39.annotation.gtf.gz
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_DIR="/path/to/your/project"
DIG_DIR="/path/to/dig-gene-set-extractors"
SRC_DIR="${PROJECT_DIR}/KidsFirst/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"

GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

mkdir -p "${PROJECT_DIR}/KidsFirst/logs"
echo "======================================================"
echo " KF + CBTN gene set extraction — Phase 2 (HZ1 top_k)"
echo " TOP_K=${TOP_K}  MIN_LOGFC=${MIN_LOGFC}  PADJ_MAX=${PADJ_MAX}"
echo " Start: $(date)"
echo "======================================================"

# KF comparisons (6 delivered)
KF_COMPARISONS=(
  "KF-TALL-vs-T21"
  "KF-TALL-vs-GTEx"
  "KF-NBL-vs-adrenal"
  "KF-ESGR-vs-muscle"
  "KF-MMC-vs-blood"
  "KF-BLOOD-vs-normal"
)

# CBTN comparisons (7 total — brain tumors vs GTEx brain cortex)
CBTN_COMPARISONS=(
  "CBTN-low_grade_glioma-vs-brain_cortex"
  "CBTN-malignant_glioma-vs-brain_cortex"
  "CBTN-medulloblastoma-vs-brain_cortex"
  "CBTN-ependymoma-vs-brain_cortex"
  "CBTN-ganglioglioma-vs-brain_cortex"
  "CBTN-craniopharyngioma-vs-brain_cortex"
  "CBTN-atypical_teratoid_rhabdoid_tumor-vs-brain_cortex"
)

# All delivered comparisons (13)
COMPARISONS=("${KF_COMPARISONS[@]}" "${CBTN_COMPARISONS[@]}")

# ── Helper: run rna_deg_multi (top_k HZ1) ─────────────────────────────────────
run_geneset() {
  local LABEL="$1" DEG_TSV="$2" OUT_DIR="$3"
  if [[ -d "$OUT_DIR" ]]; then
    echo "[SKIP] ${LABEL} $(basename $OUT_DIR) already exists"
    return
  fi
  local GTF_ARGS=()
  if [[ -n "${GTF_PATH}" && -f "${GTF_PATH}" ]]; then
    GTF_ARGS=(--gtf "${GTF_PATH}")
  fi
  PYTHONPATH="" "${GENESET_BIN}" convert rna_deg_multi \
    --deg_tsv           "$DEG_TSV" \
    --comparison_column comparison_id \
    --out_dir           "$OUT_DIR" \
    --organism          human \
    --genome_build      hg38 \
    --padj_max          "${PADJ_MAX}" \
    --min_abs_logfc     "${MIN_LOGFC}" \
    --select            top_k \
    --top_k             "${TOP_K}" \
    --gmt_topk_list     "${TOP_K}" \
    "${GTF_ARGS[@]}"
}

# ── Check gene set output sizes ───────────────────────────────────────────────
check_geneset_size() {
  local label="$1" dir="$2"
  if [[ ! -d "$dir" ]]; then
    echo "[WARN] ${label}: output directory missing: ${dir}"
    return
  fi
  local n_json n_tsv max_genes min_genes
  n_json=$(find "$dir" -name "*.json" 2>/dev/null | wc -l)
  n_tsv=$(find "$dir"  -name "*.tsv"  2>/dev/null | wc -l)
  local sizes=()
  while IFS= read -r f; do
    local n; n=$(tail -n +2 "$f" | wc -l)
    sizes+=("$n")
  done < <(find "$dir" -name "*.tsv" 2>/dev/null)
  if [[ "${#sizes[@]}" -gt 0 ]]; then
    min_genes=$(printf '%s\n' "${sizes[@]}" | sort -n | head -1 || true)
    max_genes=$(printf '%s\n' "${sizes[@]}" | sort -n | tail -1 || true)
    echo "[CHECK] ${label}: ${n_json} json + ${n_tsv} tsv files | gene set sizes: ${min_genes}–${max_genes}"
    if [[ "$min_genes" -lt 50 ]]; then
      echo "[WARN]  ${label}: smallest gene set has ${min_genes} genes (<50, PIGEAN underpowered)"
    fi
  else
    echo "[CHECK] ${label}: ${n_json} json files (no tsv found)"
  fi
}

# ── Extract HZ1 gene sets (top_k) for all delivered comparisons ───────────────
echo ""
echo "====== HZ1 gene set extraction (KF + CBTN) ======"
echo ""

for COMP in "${COMPARISONS[@]}"; do
  DEG="${ANALYSIS_DIR}/${COMP}/de_results/deg_long.tsv"
  if [[ ! -f "$DEG" ]]; then
    echo "[SKIP] ${COMP}: deg_long.tsv not found — DE not complete yet"
    continue
  fi

  echo "--- ${COMP} ---"
  run_geneset "${COMP}" "$DEG" "${ANALYSIS_DIR}/${COMP}/genesets_topk"
  check_geneset_size "${COMP}/topk" "${ANALYSIS_DIR}/${COMP}/genesets_topk"
done

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo "====== Final summary: gene sets produced ======"
echo ""
printf "%-55s  %10s\n" "Study" "topk"
echo "──────────────────────────────────────────────────────────────────────"
for COMP in "${COMPARISONS[@]}"; do
  count_dir() { [[ -d "${1}" ]] && find "${1}" -name "*.json" 2>/dev/null | wc -l || echo 0; }
  n_topk=$(count_dir "${ANALYSIS_DIR}/${COMP}/genesets_topk")
  printf "%-55s  %10s\n" "${COMP}" "${n_topk}"
done

echo ""
echo "======================================================"
echo " Phase 2 DONE: $(date)"
echo " Gene sets are in: ${ANALYSIS_DIR}/<study>/genesets_topk/"
echo "======================================================"
