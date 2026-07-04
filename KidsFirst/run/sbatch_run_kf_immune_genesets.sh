#!/bin/bash
#SBATCH --job-name=KF_immune_genesets
#SBATCH --output=KidsFirst/logs/kf_immune_%j.out
#SBATCH --error=KidsFirst/logs/kf_immune_%j.err
#SBATCH --time=08:00:00
#SBATCH --mem=64G
#SBATCH --cpus-per-task=4
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# Immune gene set extraction:
#   For each study's deg_long.tsv → split into immune / non-immune DEGs
#   → run rna_deg_multi on each subset → immune gene set + non-immune gene set
#
# Prerequisite: DE must already be complete (deg_long.tsv must exist).
# Run AFTER sbatch_run_kf_de_analysis.sh (steps 1-4) is done.
# Can also be run on category-level DE outputs (KF-BLOOD-vs-normal, KF-SOLID-vs-normal).

source /programs/biogrids.shrc
export PYTHON_X=3.9.16

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
DIG_DIR="/path/to/dig-gene-set-extractors"
SRC_DIR="${PROJECT_DIR}/KidsFirst/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"

export PYTHON_BIN="python3"
export GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

mkdir -p "${PROJECT_DIR}/KidsFirst/logs"
echo "start: $(date)"

# ── Studies to process ────────────────────────────────────────────────────────
# Each entry is the subfolder name under outputs/analysis/ that has de_results/deg_long.tsv
STUDIES=(
  "KF-TALL-vs-T21"
  "KF-TALL-vs-GTEx"
  "KF-NBL-vs-adrenal"
  "KF-ESGR-vs-muscle"
  "KF-MMC-vs-blood"
  "KF-BLOOD-vs-normal"
  "KF-SOLID-vs-normal"
  "KF-BLOOD-vs-SOLID"
)

# ── Helper: extract immune gene sets for one study ────────────────────────────
run_immune_split() {
  local STUDY_LABEL="$1"
  local DE_DIR="${ANALYSIS_DIR}/${STUDY_LABEL}/de_results"
  local DEG_TSV="${DE_DIR}/deg_long.tsv"

  if [[ ! -f "${DEG_TSV}" ]]; then
    echo "[SKIP] No deg_long.tsv found: ${STUDY_LABEL}" >&2
    return 0
  fi

  local SPLIT_DIR="${DE_DIR}/immune_split"
  local IMMUNE_DEG="${SPLIT_DIR}/deg_long_immune.tsv"
  local NONIMMUNE_DEG="${SPLIT_DIR}/deg_long_nonimmune.tsv"

  # Step 1: split DEG results into immune / non-immune
  if [[ -f "${IMMUNE_DEG}" && -f "${NONIMMUNE_DEG}" ]]; then
    echo "[split] Already split: ${STUDY_LABEL}"
  else
    echo "[split] Annotating and splitting: ${STUDY_LABEL}..."
    "${PYTHON_BIN}" "${SRC_DIR}/extract_immune_genesets.py" \
      --deg_tsv  "${DEG_TSV}" \
      --out_dir  "${SPLIT_DIR}"
  fi

  # Step 2a: gene sets from immune DEGs
  local IMMUNE_GS="${ANALYSIS_DIR}/${STUDY_LABEL}/genesets_immune"
  if [[ -d "${IMMUNE_GS}" ]]; then
    echo "[rna_deg_multi] Immune gene sets already exist: ${STUDY_LABEL}"
  else
    echo "[rna_deg_multi] Extracting immune gene sets: ${STUDY_LABEL}..."
    "${GENESET_BIN}" convert rna_deg_multi \
      --deg_tsv           "${IMMUNE_DEG}" \
      --comparison_column comparison_id \
      --out_dir           "${IMMUNE_GS}" \
      --organism          human \
      --genome_build      hg38 \
      --padj_max          0.05 \
      --min_abs_logfc     1.0 \
      --select            top_k \
      --top_k             100
  fi

  # Step 2b: gene sets from non-immune DEGs
  local NONIMMUNE_GS="${ANALYSIS_DIR}/${STUDY_LABEL}/genesets_nonimmune"
  if [[ -d "${NONIMMUNE_GS}" ]]; then
    echo "[rna_deg_multi] Non-immune gene sets already exist: ${STUDY_LABEL}"
  else
    echo "[rna_deg_multi] Extracting non-immune gene sets: ${STUDY_LABEL}..."
    "${GENESET_BIN}" convert rna_deg_multi \
      --deg_tsv           "${NONIMMUNE_DEG}" \
      --comparison_column comparison_id \
      --out_dir           "${NONIMMUNE_GS}" \
      --organism          human \
      --genome_build      hg38 \
      --padj_max          0.05 \
      --min_abs_logfc     1.0 \
      --select            top_k \
      --top_k             100
  fi

  echo "[done] ${STUDY_LABEL}"
}

# ── Run all studies ────────────────────────────────────────────────────────────
for STUDY in "${STUDIES[@]}"; do
  run_immune_split "${STUDY}"
done

echo "ALL IMMUNE GENE SET ANALYSES DONE: $(date)"

# ── Output summary ─────────────────────────────────────────────────────────────
echo ""
echo "=== Gene set output summary ==="
for STUDY in "${STUDIES[@]}"; do
  IMMUNE_GS="${ANALYSIS_DIR}/${STUDY}/genesets_immune"
  NONIMMUNE_GS="${ANALYSIS_DIR}/${STUDY}/genesets_nonimmune"
  N_IMMUNE=$(find "${IMMUNE_GS}" -name "*.json" 2>/dev/null | wc -l || echo 0)
  N_NONIMMUNE=$(find "${NONIMMUNE_GS}" -name "*.json" 2>/dev/null | wc -l || echo 0)
  echo "  ${STUDY}: immune=${N_IMMUNE} non-immune=${N_NONIMMUNE} gene set files"
done
