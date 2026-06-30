#!/bin/bash
#SBATCH --job-name=CBTN_DE
#SBATCH --output=KidsFirst_DE_Analysis/logs/cbtn_de_%j.out
#SBATCH --error=KidsFirst_DE_Analysis/logs/cbtn_de_%j.err
#SBATCH --time=16:00:00
#SBATCH --mem=128G
#SBATCH --cpus-per-task=8
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# ── CBTN DE analysis ──────────────────────────────────────────────────────────
# Prerequisite: sbatch_01b_build_cbtn_matrices.sh must be complete.
#
# Comparisons (7 total — each brain tumor diagnosis vs GTEx brain cortex):
#   CBTN-low_grade_glioma-vs-brain_cortex
#   CBTN-malignant_glioma-vs-brain_cortex
#   CBTN-medulloblastoma-vs-brain_cortex
#   CBTN-ependymoma-vs-brain_cortex
#   CBTN-ganglioglioma-vs-brain_cortex
#   CBTN-craniopharyngioma-vs-brain_cortex
#   CBTN-atypical_teratoid_rhabdoid_tumor-vs-brain_cortex
#
# Normal reference: GTEx Brain - Cortex (outputs/analysis/gtex/brain_cortex.tsv)
# ─────────────────────────────────────────────────────────────────────────────

source /programs/biogrids.shrc
export PYTHON_X=3.9.16
unset PYTHONPATH

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
DIG_DIR="/path/to/dig-gene-set-extractors"
SRC_DIR="${PROJECT_DIR}/KidsFirst_DE_Analysis/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"
GENE_MAP="${PROJECT_DIR}/inputs/ensg_to_symbol.tsv"

PYTHON_BIN="python3"
GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

GTEX_BRAIN="${ANALYSIS_DIR}/gtex/brain_cortex.tsv"

mkdir -p "${PROJECT_DIR}/KidsFirst_DE_Analysis/logs"
echo "======================================================"
echo " CBTN DE analysis — brain tumors vs GTEx brain cortex"
echo " Start: $(date)"
echo "======================================================"

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [[ ! -f "$GTEX_BRAIN" ]]; then
  echo "[ERROR] GTEx brain cortex not found: ${GTEX_BRAIN}"
  echo "        Run sbatch_01b_build_cbtn_matrices.sh first"
  exit 1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
check_matrix() {
  local label="$1" f="$2"
  if [[ ! -f "$f" ]]; then echo "[ERROR] Missing matrix: $f"; exit 1; fi
  local genes samples
  genes=$(tail -n +2 "$f" | wc -l)
  samples=$(head -1 "$f" | awk -F'\t' '{print NF-1}')
  echo "[CHECK] ${label}: ${genes} genes × ${samples} samples"
  if [[ "$genes" -lt 10000 ]]; then
    echo "[WARN]  ${label}: <10,000 genes — verify Ensembl ID stripping"
  fi
  if [[ "$samples" -lt 2 ]]; then
    echo "[ERROR] ${label}: <2 samples"; exit 1
  fi
}

check_deg() {
  local label="$1" f="$2"
  if [[ ! -f "$f" ]]; then echo "[ERROR] Missing DEG: $f"; exit 1; fi
  local total sig sig_fc
  total=$(tail -n +2 "$f" | wc -l)
  sig=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05' "$f" | wc -l)
  sig_fc=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && ($4+0>1||$4+0<-1)' "$f" | wc -l)
  echo "[CHECK] ${label} DEG: tested=${total} | padj<0.05: ${sig} | padj<0.05+|logFC|≥1: ${sig_fc}"
  if [[ "$sig_fc" -lt 50 ]]; then
    echo "[WARN]  ${label}: only ${sig_fc} genes at padj<0.05+|logFC|≥1 — check data/thresholds"
  fi
  echo "[CHECK] ${label} top 5 upregulated genes:"
  awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && $4+0>0 {print $4"\t"$3}' "$f" \
    | sort -k1,1rn | head -5 | awk '{printf "        logFC=%-8s %s\n", $1, $2}' || true
}

# ── DE function ───────────────────────────────────────────────────────────────
run_de() {
  local LABEL="$1" TUMOR="$2"
  local OUT_DIR="${ANALYSIS_DIR}/${LABEL}"
  mkdir -p "${OUT_DIR}/de_inputs" "${OUT_DIR}/de_results"

  # Verify tumor matrix exists
  if [[ ! -f "$TUMOR" ]]; then
    echo "[ERROR] Tumor matrix not found: ${TUMOR}"
    echo "        Run sbatch_01b_build_cbtn_matrices.sh first"
    exit 1
  fi

  # Step 1: merge tumor + brain cortex normal
  if [[ ! -f "${OUT_DIR}/de_inputs/combined_counts.tsv" ]]; then
    echo "[RUN] prepare_de_inputs: ${LABEL}..."
    "${PYTHON_BIN}" "${SRC_DIR}/prepare_de_inputs.py" \
      --tumor_counts  "$TUMOR" \
      --normal_counts "$GTEX_BRAIN" \
      --study_id      "$LABEL" \
      --out_dir       "${OUT_DIR}/de_inputs" \
      --gene_map_tsv  "${GENE_MAP}"
    check_matrix "${LABEL}/combined" "${OUT_DIR}/de_inputs/combined_counts.tsv"
    local n_tumor n_normal
    n_tumor=$(awk -F'\t' 'NR>1 && $2=="tumor"' "${OUT_DIR}/de_inputs/sample_metadata.tsv" | wc -l)
    n_normal=$(awk -F'\t' 'NR>1 && $2=="normal"' "${OUT_DIR}/de_inputs/sample_metadata.tsv" | wc -l)
    echo "[CHECK] ${LABEL} sample_metadata: ${n_tumor} tumor, ${n_normal} normal"
    if [[ "$n_tumor" -lt 2 || "$n_normal" -lt 2 ]]; then
      echo "[ERROR] ${LABEL}: need ≥2 samples per group for DE"; exit 1
    fi
  else
    echo "[SKIP] ${LABEL} de_inputs already exist"
  fi

  # Step 2: limma-voom DE
  if [[ ! -f "${OUT_DIR}/de_results/deg_long.tsv" ]]; then
    echo "[RUN] rna_de_prepare: ${LABEL}..."
    PYTHONPATH="" "${GENESET_BIN}" workflows rna_de_prepare \
      --modality                  bulk \
      --counts_tsv                "${OUT_DIR}/de_inputs/combined_counts.tsv" \
      --matrix_orientation        gene_by_sample \
      --sample_metadata_tsv       "${OUT_DIR}/de_inputs/sample_metadata.tsv" \
      --sample_id_column          sample_id \
      --feature_id_column         gene_id \
      --matrix_gene_symbol_column gene_symbol \
      --group_column              condition \
      --comparison_mode           condition_a_vs_b \
      --condition_a               tumor \
      --condition_b               normal \
      --backend                   r_limma_voom \
      --de_mode                   modern \
      --out_dir                   "${OUT_DIR}/de_results"
  else
    echo "[SKIP] ${LABEL} de_results already exist"
  fi

  check_deg "${LABEL}" "${OUT_DIR}/de_results/deg_long.tsv"
}

# ── Run all 7 CBTN comparisons ────────────────────────────────────────────────
echo ""
echo "====== CBTN DE: brain tumors vs GTEx Brain - Cortex ======"
echo ""

run_de "CBTN-low_grade_glioma-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-low_grade_glioma/rsem_counts.tsv"

run_de "CBTN-malignant_glioma-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-malignant_glioma/rsem_counts.tsv"

run_de "CBTN-medulloblastoma-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-medulloblastoma/rsem_counts.tsv"

run_de "CBTN-ependymoma-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-ependymoma/rsem_counts.tsv"

run_de "CBTN-ganglioglioma-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-ganglioglioma/rsem_counts.tsv"

run_de "CBTN-craniopharyngioma-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-craniopharyngioma/rsem_counts.tsv"

run_de "CBTN-atypical_teratoid_rhabdoid_tumor-vs-brain_cortex" \
  "${ANALYSIS_DIR}/CBTN-atypical_teratoid_rhabdoid_tumor/rsem_counts.tsv"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "====== Summary ======"
echo ""
echo "DEG quick summary (padj<0.05 + |logFC|≥1):"
for SLUG in low_grade_glioma malignant_glioma medulloblastoma ependymoma \
            ganglioglioma craniopharyngioma atypical_teratoid_rhabdoid_tumor; do
  DEG="${ANALYSIS_DIR}/CBTN-${SLUG}-vs-brain_cortex/de_results/deg_long.tsv"
  if [[ -f "$DEG" ]]; then
    up=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && $4+0>1'  "$DEG" | wc -l)
    dn=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && $4+0<-1' "$DEG" | wc -l)
    printf "  %-55s  up=%-6s  down=%-6s\n" "CBTN-${SLUG}" "${up}" "${dn}"
  else
    printf "  %-55s  MISSING\n" "CBTN-${SLUG}"
  fi
done

echo ""
echo "======================================================"
echo " CBTN DE DONE: $(date)"
echo " Next: add CBTN comparisons to sbatch_03_extract_genesets.sh"
echo "======================================================"
