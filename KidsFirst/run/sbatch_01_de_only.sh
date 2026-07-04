#!/bin/bash
#SBATCH --job-name=KF_DE_only
#SBATCH --output=KidsFirst/logs/kf_de_only_%j.out
#SBATCH --error=KidsFirst/logs/kf_de_only_%j.err
#SBATCH --time=16:00:00
#SBATCH --mem=128G
#SBATCH --cpus-per-task=8
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# ── PHASE 1 of 2-phase workflow ───────────────────────────────────────────────
# This script: build count matrices + run all 8 DE analyses (NO gene set extraction)
# After this completes:
#   1. bash KidsFirst/run/02_check_natural_sizes.sh  ← see gene counts
#   2. Decide TOP_K and MIN_LOGFC in sbatch_03_extract_genesets.sh
#   3. sbatch KidsFirst/run/sbatch_03_extract_genesets.sh
#
# Comparisons (8 total — see analysis_design.md for scientific rationale):
#   KF-TALL-vs-T21       T-ALL vs Down syndrome blood (primary, pediatric-matched)
#   KF-TALL-vs-GTEx      T-ALL vs GTEx whole blood (secondary validation)
#   KF-NBL-vs-adrenal    Neuroblastoma vs GTEx adrenal gland
#   KF-ESGR-vs-muscle    Ewing sarcoma vs GTEx skeletal muscle
#   KF-MMC-vs-blood      AML vs GTEx whole blood
#   KF-TALL-vs-MMC       T-cell vs myeloid lineage contrast (NEW)
#   KF-BLOOD-vs-normal   Pan-blood cancer (TALL+MMC) vs GTEx whole blood
#   KF-BLOOD-vs-SOLID    Pan-blood cancer vs pan-solid cancer (internal contrast)
#
# Note: KF-SOLID-vs-normal excluded (scientifically rejected — see analysis_design.md §2)
# ─────────────────────────────────────────────────────────────────────────────

source /programs/biogrids.shrc
export PYTHON_X=3.9.16
unset PYTHONPATH

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
DIG_DIR="/path/to/dig-gene-set-extractors"
SRC_DIR="${PROJECT_DIR}/KidsFirst/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"
GTEX_DIR="${PROJECT_DIR}/inputs/GTEx/v10"
GTEX_ATTRS="${GTEX_DIR}/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt"
WORKERS="${SLURM_CPUS_PER_TASK:-8}"

PYTHON_BIN="python3"
GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"
GENE_MAP="${PROJECT_DIR}/inputs/ensg_to_symbol.tsv"

mkdir -p "${PROJECT_DIR}/KidsFirst/logs" "${ANALYSIS_DIR}/gtex"
echo "======================================================"
echo " KF DE analysis — Phase 1: matrices + DE"
echo " Start: $(date)"
echo "======================================================"

# ── Sanity check helpers ──────────────────────────────────────────────────────
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
  # Columns: comparison_id(1) gene_id(2) gene_symbol(3) logFC(4) stat(5) pvalue(6) padj(7)
  local total sig sig_fc
  total=$(tail -n +2 "$f" | wc -l)
  sig=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05' "$f" | wc -l)
  sig_fc=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && ($4+0>1||$4+0<-1)' "$f" | wc -l)
  echo "[CHECK] ${label} DEG: tested=${total} | padj<0.05: ${sig} | padj<0.05+|logFC|≥1: ${sig_fc}"
  if [[ "$sig_fc" -lt 50 ]]; then
    echo "[WARN]  ${label}: only ${sig_fc} genes at padj<0.05+|logFC|≥1 — check data/thresholds"
  fi
  # Show top 5 upregulated by logFC (sanity: should look like cancer genes)
  echo "[CHECK] ${label} top 5 upregulated genes:"
  awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && $4+0>0 {print $4"\t"$3}' "$f" \
    | sort -k1,1rn | head -5 | awk '{printf "        logFC=%-8s %s\n", $1, $2}' || true
}

# ── PHASE A: Build individual RSEM matrices ───────────────────────────────────
echo ""
echo "====== PHASE A: Build RSEM count matrices ======"

build_rsem() {
  local LABEL="$1" STUDY_DIR="$2"
  local OUT="${ANALYSIS_DIR}/${LABEL}/rsem_counts.tsv"
  mkdir -p "${ANALYSIS_DIR}/${LABEL}"
  if [[ -f "$OUT" ]]; then
    echo "[SKIP] ${LABEL} rsem_counts.tsv already exists"
    check_matrix "${LABEL}" "$OUT"
    return
  fi
  echo "[RUN] Building RSEM matrix: ${LABEL}..."
  "${PYTHON_BIN}" "${SRC_DIR}/build_rsem_matrix.py" \
    --rsem_dir     "${STUDY_DIR}/outputs/rsem_files" \
    --manifest_tsv "${STUDY_DIR}/config/rsem_manifest.tsv" \
    --out_tsv      "$OUT" \
    --workers      "${WORKERS}"
  check_matrix "${LABEL}" "$OUT"
}

build_rsem "KF-TALL" "${PROJECT_DIR}/KidsFirst_KF_TALL"
build_rsem "KF-MMC"  "${PROJECT_DIR}/KidsFirst_KF_MMC"
build_rsem "KF-NBL"  "${PROJECT_DIR}/KidsFirst_KF_NBL"
build_rsem "KF-ESGR" "${PROJECT_DIR}/KidsFirst_KF_ESGR"
build_rsem "KF-T21"  "${PROJECT_DIR}/KidsFirst_KF_CHDALL"

# ── PHASE B: Extract GTEx normal counts (shared cache) ───────────────────────
echo ""
echo "====== PHASE B: Extract GTEx normal counts ======"

extract_gtex() {
  local LABEL="$1" GCT="$2" TISSUE="$3"
  local OUT="${ANALYSIS_DIR}/gtex/${LABEL}.tsv"
  if [[ -f "$OUT" ]]; then
    echo "[SKIP] GTEx ${LABEL} already extracted"
    check_matrix "GTEx/${LABEL}" "$OUT"
    return
  fi
  echo "[RUN] Extracting GTEx: ${TISSUE}..."
  "${PYTHON_BIN}" "${SRC_DIR}/extract_gtex_counts.py" \
    --gct          "${GTEX_DIR}/${GCT}" \
    --sample_attrs "${GTEX_ATTRS}" \
    --tissue       "${TISSUE}" \
    --out_tsv      "$OUT"
  check_matrix "GTEx/${LABEL}" "$OUT"
}

extract_gtex "whole_blood" "gene_reads_v10_whole_blood.gct.gz"     "Whole Blood"
extract_gtex "adrenal"     "gene_reads_v10_adrenal_gland.gct.gz"   "Adrenal Gland"
extract_gtex "muscle"      "gene_reads_v10_muscle_skeletal.gct.gz" "Muscle - Skeletal"

# ── PHASE C: Build merged category matrices ───────────────────────────────────
echo ""
echo "====== PHASE C: Merge category matrices ======"

build_merged() {
  local LABEL="$1"; shift
  local OUT="${ANALYSIS_DIR}/${LABEL}/merged_tumor.tsv"
  local META="${ANALYSIS_DIR}/${LABEL}/merged_tumor_membership.tsv"
  mkdir -p "${ANALYSIS_DIR}/${LABEL}"
  if [[ -f "$OUT" ]]; then
    echo "[SKIP] ${LABEL} merged_tumor.tsv already exists"
    check_matrix "${LABEL}/merged" "$OUT"
    return
  fi
  echo "[RUN] Merging: ${LABEL}..."
  local inputs=() study_ids=()
  while [[ $# -gt 0 ]]; do
    local key="$1"; local val="$2"; shift 2
    if [[ "$key" == "--input" ]]; then inputs+=("$val")
    elif [[ "$key" == "--study" ]]; then study_ids+=("$val")
    fi
  done
  "${PYTHON_BIN}" "${SRC_DIR}/merge_study_matrices.py" \
    --inputs       "${inputs[@]}" \
    --study_ids    "${study_ids[@]}" \
    --out_tsv      "$OUT" \
    --out_metadata_tsv "$META"
  check_matrix "${LABEL}/merged" "$OUT"
}

build_merged "KF-BLOOD" \
  --input "${ANALYSIS_DIR}/KF-TALL/rsem_counts.tsv" --study "KF-TALL" \
  --input "${ANALYSIS_DIR}/KF-MMC/rsem_counts.tsv"  --study "KF-MMC"

build_merged "KF-SOLID" \
  --input "${ANALYSIS_DIR}/KF-NBL/rsem_counts.tsv"  --study "KF-NBL" \
  --input "${ANALYSIS_DIR}/KF-ESGR/rsem_counts.tsv" --study "KF-ESGR"

# ── PHASE D: Run all 8 DE analyses ───────────────────────────────────────────
echo ""
echo "====== PHASE D: Differential expression (limma-voom) ======"

run_de() {
  local LABEL="$1" TUMOR="$2" NORMAL="$3"
  local OUT_DIR="${ANALYSIS_DIR}/${LABEL}"
  mkdir -p "${OUT_DIR}/de_inputs" "${OUT_DIR}/de_results"

  # Step D1: merge counts + create sample_metadata
  if [[ ! -f "${OUT_DIR}/de_inputs/combined_counts.tsv" ]]; then
    echo "[RUN] prepare_de_inputs: ${LABEL}..."
    "${PYTHON_BIN}" "${SRC_DIR}/prepare_de_inputs.py" \
      --tumor_counts  "$TUMOR" \
      --normal_counts "$NORMAL" \
      --study_id      "$LABEL" \
      --out_dir       "${OUT_DIR}/de_inputs" \
      --gene_map_tsv  "${GENE_MAP}"
    check_matrix "${LABEL}/combined" "${OUT_DIR}/de_inputs/combined_counts.tsv"
    # Verify sample_metadata has both conditions
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

  # Step D2: limma-voom DE
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

echo ""
echo "-- Individual studies --"
run_de "KF-TALL-vs-T21" \
  "${ANALYSIS_DIR}/KF-TALL/rsem_counts.tsv" \
  "${ANALYSIS_DIR}/KF-T21/rsem_counts.tsv"

run_de "KF-TALL-vs-GTEx" \
  "${ANALYSIS_DIR}/KF-TALL/rsem_counts.tsv" \
  "${ANALYSIS_DIR}/gtex/whole_blood.tsv"

run_de "KF-NBL-vs-adrenal" \
  "${ANALYSIS_DIR}/KF-NBL/rsem_counts.tsv" \
  "${ANALYSIS_DIR}/gtex/adrenal.tsv"

run_de "KF-ESGR-vs-muscle" \
  "${ANALYSIS_DIR}/KF-ESGR/rsem_counts.tsv" \
  "${ANALYSIS_DIR}/gtex/muscle.tsv"

run_de "KF-MMC-vs-blood" \
  "${ANALYSIS_DIR}/KF-MMC/rsem_counts.tsv" \
  "${ANALYSIS_DIR}/gtex/whole_blood.tsv"

echo ""
echo "-- Lineage contrast --"
# TALL (T-cell) as 'tumor', MMC (myeloid) as 'normal' — directionality label only
run_de "KF-TALL-vs-MMC" \
  "${ANALYSIS_DIR}/KF-TALL/rsem_counts.tsv" \
  "${ANALYSIS_DIR}/KF-MMC/rsem_counts.tsv"

echo ""
echo "-- Category analyses --"
run_de "KF-BLOOD-vs-normal" \
  "${ANALYSIS_DIR}/KF-BLOOD/merged_tumor.tsv" \
  "${ANALYSIS_DIR}/gtex/whole_blood.tsv"

# KF-SOLID used as 'normal' (reference) for blood vs solid contrast
run_de "KF-BLOOD-vs-SOLID" \
  "${ANALYSIS_DIR}/KF-BLOOD/merged_tumor.tsv" \
  "${ANALYSIS_DIR}/KF-SOLID/merged_tumor.tsv"

# ── PHASE E: Summary ──────────────────────────────────────────────────────────
echo ""
echo "====== PHASE E: Summary ======"
echo ""
echo "DEG quick summary (padj<0.05 + |logFC|≥1):"
for COMP in KF-TALL-vs-T21 KF-TALL-vs-GTEx KF-NBL-vs-adrenal KF-ESGR-vs-muscle \
            KF-MMC-vs-blood KF-TALL-vs-MMC KF-BLOOD-vs-normal KF-BLOOD-vs-SOLID; do
  DEG="${ANALYSIS_DIR}/${COMP}/de_results/deg_long.tsv"
  if [[ -f "$DEG" ]]; then
    up=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && $4+0>1'  "$DEG" | wc -l)
    dn=$(awk -F'\t' 'NR>1 && $7!="NA" && $7+0<0.05 && $4+0<-1' "$DEG" | wc -l)
    printf "  %-30s  up=%-6s  down=%-6s\n" "${COMP}" "${up}" "${dn}"
  else
    printf "  %-30s  MISSING\n" "${COMP}"
  fi
done

echo ""
echo "======================================================"
echo " Phase 1 DONE: $(date)"
echo " Next: bash KidsFirst/run/02_check_natural_sizes.sh"
echo "======================================================"
