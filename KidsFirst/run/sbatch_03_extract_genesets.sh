#!/bin/bash
#SBATCH --job-name=KF_genesets
#SBATCH --output=KidsFirst_DE_Analysis/logs/kf_genesets_%j.out
#SBATCH --error=KidsFirst_DE_Analysis/logs/kf_genesets_%j.err
#SBATCH --time=04:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=4
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# ── PHASE 2 of 2-phase workflow ───────────────────────────────────────────────
# Prerequisites:
#   sbatch_01_de_only.sh  (KF 8 comparisons)
#   sbatch_02_cbtn.de.sh  (CBTN 7 comparisons) — skipped gracefully if not done
# Run 02_check_natural_sizes.sh first to decide TOP_K and MIN_LOGFC below.
#
# This script produces TWO versions per comparison:
#   genesets_natural/  padj<PADJ, |logFC|≥MIN_LOGFC, no top_k cap
#                      → shows natural landscape size
#   genesets_topk/     padj<PADJ, |logFC|≥MIN_LOGFC, top_k=TOP_K
#                      → curated size for GWAS / delivery
#
# Then runs immune annotation on the TOP_K version (KF blood/solid only):
#   genesets_immune/      top_k immune DEGs
#   genesets_nonimmune/   top_k non-immune DEGs
# ─────────────────────────────────────────────────────────────────────────────

source /programs/biogrids.shrc
export PYTHON_X=3.9.16
unset PYTHONPATH

set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════════
# USER CONFIGURATION — edit after reviewing 02_check_natural_sizes.sh output
# ══════════════════════════════════════════════════════════════════════════════
TOP_K=100          # Cap for curated gene sets (genesets_topk/)
MIN_LOGFC="1.0"    # |log2FC| threshold (try 1.5 or 2.0 if natural sizes are very large)
PADJ_MAX="0.05"    # FDR threshold
# GTF for gene symbol annotation (GENCODE v39, hg38 — matches GTEx v10 quantification).
# Download: https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_39/gencode.v39.annotation.gtf.gz
# Set to "" to skip annotation (gene_symbol will fall back to Ensembl IDs; immune regex will not work).
GTF_PATH=""        # e.g. /path/to/gencode.v39.annotation.gtf.gz
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_DIR="/lab-share/RC-Data-Science-e2/Groups/gnomad/kyuryung/geneset-extractor-dev/KidsFirst_non_CBTN"
DIG_DIR="/lab-share/RC-Data-Science-e2/Groups/gnomad/kyuryung/dig-gene-set-extractors"
SRC_DIR="${PROJECT_DIR}/KidsFirst_DE_Analysis/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"

PYTHON_BIN="python3"
GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

mkdir -p "${PROJECT_DIR}/KidsFirst_DE_Analysis/logs"
echo "======================================================"
echo " KF + CBTN gene set extraction — Phase 2"
echo " TOP_K=${TOP_K}  MIN_LOGFC=${MIN_LOGFC}  PADJ_MAX=${PADJ_MAX}"
echo " Start: $(date)"
echo "======================================================"

# KF comparisons (8 total)
KF_COMPARISONS=(
  "KF-TALL-vs-T21"
  "KF-TALL-vs-GTEx"
  "KF-NBL-vs-adrenal"
  "KF-ESGR-vs-muscle"
  "KF-MMC-vs-blood"
  "KF-TALL-vs-MMC"
  "KF-BLOOD-vs-normal"
  "KF-BLOOD-vs-SOLID"
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

# All comparisons combined
COMPARISONS=("${KF_COMPARISONS[@]}" "${CBTN_COMPARISONS[@]}")

# Studies that get immune split (blood/solid tumors only — not brain tumors)
IMMUNE_COMPARISONS=(
  "KF-TALL-vs-GTEx"
  "KF-NBL-vs-adrenal"
  "KF-MMC-vs-blood"
  "KF-TALL-vs-MMC"
  "KF-BLOOD-vs-normal"
  "KF-BLOOD-vs-SOLID"
)

# ── Helper: run rna_deg_multi ─────────────────────────────────────────────────
run_geneset() {
  local LABEL="$1" DEG_TSV="$2" OUT_DIR="$3" USE_TOPK="$4"
  if [[ -d "$OUT_DIR" ]]; then
    echo "[SKIP] ${LABEL} $(basename $OUT_DIR) already exists"
    return
  fi
  local GTF_ARGS=()
  if [[ -n "${GTF_PATH}" && -f "${GTF_PATH}" ]]; then
    GTF_ARGS=(--gtf "${GTF_PATH}")
  fi
  if [[ "$USE_TOPK" == "yes" ]]; then
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
  else
    # Natural: high top_k = effectively no cap
    PYTHONPATH="" "${GENESET_BIN}" convert rna_deg_multi \
      --deg_tsv           "$DEG_TSV" \
      --comparison_column comparison_id \
      --out_dir           "$OUT_DIR" \
      --organism          human \
      --genome_build      hg38 \
      --padj_max          "${PADJ_MAX}" \
      --min_abs_logfc     "${MIN_LOGFC}" \
      --select            top_k \
      --top_k             9999 \
      --gmt_topk_list     9999 \
      "${GTF_ARGS[@]}"
  fi
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

# ── Step 1: Extract gene sets (both versions) for all comparisons ─────────────
echo ""
echo "====== Step 1: Gene set extraction (KF + CBTN) ======"
echo ""

for COMP in "${COMPARISONS[@]}"; do
  DEG="${ANALYSIS_DIR}/${COMP}/de_results/deg_long.tsv"
  if [[ ! -f "$DEG" ]]; then
    echo "[SKIP] ${COMP}: deg_long.tsv not found — DE not complete yet"
    continue
  fi

  echo "--- ${COMP} ---"
  run_geneset "${COMP}" "$DEG" "${ANALYSIS_DIR}/${COMP}/genesets_topk"     "yes"
  run_geneset "${COMP}" "$DEG" "${ANALYSIS_DIR}/${COMP}/genesets_natural"  "no"
  check_geneset_size "${COMP}/topk"     "${ANALYSIS_DIR}/${COMP}/genesets_topk"
  check_geneset_size "${COMP}/natural"  "${ANALYSIS_DIR}/${COMP}/genesets_natural"
done

# ── Step 2: Immune annotation + split (KF blood/solid comparisons only) ───────
echo ""
echo "====== Step 2: Immune gene set extraction (KF only) ======"
echo ""

for COMP in "${IMMUNE_COMPARISONS[@]}"; do
  DEG="${ANALYSIS_DIR}/${COMP}/de_results/deg_long.tsv"
  if [[ ! -f "$DEG" ]]; then
    echo "[SKIP] ${COMP}: deg_long.tsv not found"
    continue
  fi
  SPLIT_DIR="${ANALYSIS_DIR}/${COMP}/de_results/immune_split"
  IMMUNE_DEG="${SPLIT_DIR}/deg_long_immune.tsv"
  NONIMMUNE_DEG="${SPLIT_DIR}/deg_long_nonimmune.tsv"
  echo "--- ${COMP} ---"

  if [[ -f "$IMMUNE_DEG" && -f "$NONIMMUNE_DEG" ]]; then
    echo "[SKIP] ${COMP} immune split already exists"
  else
    echo "[RUN] Splitting immune/non-immune: ${COMP}..."
    "${PYTHON_BIN}" "${SRC_DIR}/extract_immune_genesets.py" \
      --deg_tsv "$DEG" \
      --out_dir "$SPLIT_DIR"
    local_immune=$(tail -n +2 "$IMMUNE_DEG" | wc -l)
    local_nonimmune=$(tail -n +2 "$NONIMMUNE_DEG" | wc -l)
    local_sig_immune=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && ($4+0>1||$4+0<-1)' "$IMMUNE_DEG" | wc -l)
    local_sig_nonimmune=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && ($4+0>1||$4+0<-1)' "$NONIMMUNE_DEG" | wc -l)
    echo "[CHECK] ${COMP} split: ${local_immune} immune rows (${local_sig_immune} sig), ${local_nonimmune} non-immune rows (${local_sig_nonimmune} sig)"
  fi

  run_geneset "${COMP}/immune"    "$IMMUNE_DEG"    "${ANALYSIS_DIR}/${COMP}/genesets_immune"    "yes"
  run_geneset "${COMP}/nonimmune" "$NONIMMUNE_DEG" "${ANALYSIS_DIR}/${COMP}/genesets_nonimmune" "yes"
  check_geneset_size "${COMP}/immune"    "${ANALYSIS_DIR}/${COMP}/genesets_immune"
  check_geneset_size "${COMP}/nonimmune" "${ANALYSIS_DIR}/${COMP}/genesets_nonimmune"
done

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo "====== Final summary: gene sets produced ======"
echo ""
printf "%-55s  %10s  %10s  %10s  %10s\n" "Study" "topk" "natural" "immune" "nonimmune"
echo "────────────────────────────────────────────────────────────────────────────────────────────"
for COMP in "${COMPARISONS[@]}"; do
  count_dir() { [[ -d "${1}" ]] && find "${1}" -name "*.json" 2>/dev/null | wc -l || echo 0; }
  n_topk=$(count_dir     "${ANALYSIS_DIR}/${COMP}/genesets_topk")
  n_nat=$(count_dir      "${ANALYSIS_DIR}/${COMP}/genesets_natural")
  n_imm=$(count_dir      "${ANALYSIS_DIR}/${COMP}/genesets_immune")
  n_nonimm=$(count_dir   "${ANALYSIS_DIR}/${COMP}/genesets_nonimmune")
  printf "%-55s  %10s  %10s  %10s  %10s\n" "${COMP}" "${n_topk}" "${n_nat}" "${n_imm}" "${n_nonimm}"
done

echo ""
echo "======================================================"
echo " Phase 2 DONE: $(date)"
echo " Gene sets are in: ${ANALYSIS_DIR}/<study>/genesets_topk/"
echo "======================================================"
