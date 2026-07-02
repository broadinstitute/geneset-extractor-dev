#!/bin/bash
#SBATCH --job-name=KF_category_DE
#SBATCH --output=KidsFirst_DE_Analysis/logs/kf_category_%j.out
#SBATCH --error=KidsFirst_DE_Analysis/logs/kf_category_%j.err
#SBATCH --time=16:00:00
#SBATCH --mem=128G
#SBATCH --cpus-per-task=8
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

# Category-level DE analysis:
#   KF-BLOOD (TALL + MMC) vs GTEx Whole Blood  → pan-pediatric blood cancer gene set
#   KF-SOLID (NBL + ESGR) vs GTEx Adrenal+Muscle → pan-pediatric solid cancer gene set
#   KF-BLOOD vs KF-SOLID (internal)             → tissue category contrast
#
# Prerequisite: individual study rsem_counts.tsv must already exist
# (run sbatch_run_kf_de_analysis.sh steps 1-2 first, or this script builds them)

source /programs/biogrids.shrc
export PYTHON_X=3.9.16

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
DIG_DIR="/path/to/dig-gene-set-extractors"
SCRIPT_DIR="${PROJECT_DIR}/KidsFirst_DE_Analysis/run"
SRC_DIR="${PROJECT_DIR}/KidsFirst_DE_Analysis/src"
ANALYSIS_DIR="${PROJECT_DIR}/outputs/analysis"
GTEX_DIR="${PROJECT_DIR}/inputs/GTEx/v10"
WORKERS="${SLURM_CPUS_PER_TASK:-8}"

export PYTHON_BIN="python3"
export GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

mkdir -p "${PROJECT_DIR}/KidsFirst_DE_Analysis/logs"
echo "start: $(date)"

# ── Helper: ensure individual study RSEM matrix exists ──────────────────────
ensure_rsem_matrix() {
  local STUDY="$1"
  local MATRIX="${ANALYSIS_DIR}/${STUDY}/rsem_counts.tsv"
  if [[ ! -f "${MATRIX}" ]]; then
    echo "[build_rsem] Building ${STUDY}..."
    "${PYTHON_BIN}" "${SRC_DIR}/build_rsem_matrix.py" \
      --rsem_dir     "${PROJECT_DIR}/${STUDY}/outputs/rsem_files" \
      --manifest_tsv "${PROJECT_DIR}/${STUDY}/config/rsem_manifest.tsv" \
      --out_tsv      "${MATRIX}" \
      --workers      "${WORKERS}"
  else
    echo "[build_rsem] Already exists: ${STUDY}"
  fi
  echo "${MATRIX}"
}

# ── Step A: build individual matrices (if not already done) ──────────────────
TALL_MATRIX=$(ensure_rsem_matrix "KidsFirst_KF_TALL")
MMC_MATRIX=$(ensure_rsem_matrix "KidsFirst_KF_MMC")
NBL_MATRIX=$(ensure_rsem_matrix "KidsFirst_KF_NBL")
ESGR_MATRIX=$(ensure_rsem_matrix "KidsFirst_KF_ESGR")

# ── Step B: Merge into category matrices ─────────────────────────────────────
BLOOD_DIR="${ANALYSIS_DIR}/KF-BLOOD"
SOLID_DIR="${ANALYSIS_DIR}/KF-SOLID"
mkdir -p "${BLOOD_DIR}" "${SOLID_DIR}"

BLOOD_TUMOR="${BLOOD_DIR}/merged_tumor_counts.tsv"
if [[ ! -f "${BLOOD_TUMOR}" ]]; then
  echo "[merge] Building KF-BLOOD (TALL + MMC)..."
  "${PYTHON_BIN}" "${SRC_DIR}/merge_study_matrices.py" \
    --inputs   "${TALL_MATRIX}" "${MMC_MATRIX}" \
    --study_ids KF-TALL KF-MMC \
    --out_tsv  "${BLOOD_TUMOR}" \
    --out_metadata_tsv "${BLOOD_DIR}/tumor_study_membership.tsv"
fi

SOLID_TUMOR="${SOLID_DIR}/merged_tumor_counts.tsv"
if [[ ! -f "${SOLID_TUMOR}" ]]; then
  echo "[merge] Building KF-SOLID (NBL + ESGR)..."
  "${PYTHON_BIN}" "${SRC_DIR}/merge_study_matrices.py" \
    --inputs   "${NBL_MATRIX}" "${ESGR_MATRIX}" \
    --study_ids KF-NBL KF-ESGR \
    --out_tsv  "${SOLID_TUMOR}" \
    --out_metadata_tsv "${SOLID_DIR}/tumor_study_membership.tsv"
fi

# ── Step C: Extract GTEx normals ──────────────────────────────────────────────
GTEX_BLOOD="${BLOOD_DIR}/gtex_normal_counts.tsv"
if [[ ! -f "${GTEX_BLOOD}" ]]; then
  echo "[gtex] Extracting GTEx Whole Blood..."
  "${PYTHON_BIN}" "${SRC_DIR}/extract_gtex_counts.py" \
    --gct          "${GTEX_DIR}/gene_reads_v10_whole_blood.gct.gz" \
    --sample_attrs "${GTEX_DIR}/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt" \
    --tissue       "Whole Blood" \
    --out_tsv      "${GTEX_BLOOD}"
fi

# For solid tumors: use adrenal gland as reference
# (NBL is adrenal-primary; ESGR is mesenchymal but adrenal is less biased than muscle
#  for a combined comparison — the shared signal will survive either choice)
GTEX_SOLID="${SOLID_DIR}/gtex_normal_counts.tsv"
if [[ ! -f "${GTEX_SOLID}" ]]; then
  echo "[gtex] Extracting GTEx Adrenal Gland (solid tumor reference)..."
  "${PYTHON_BIN}" "${SRC_DIR}/extract_gtex_counts.py" \
    --gct          "${GTEX_DIR}/gene_reads_v10_adrenal_gland.gct.gz" \
    --sample_attrs "${GTEX_DIR}/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt" \
    --tissue       "Adrenal Gland" \
    --out_tsv      "${GTEX_SOLID}"
fi

# ── Step D: prepare_de_inputs for each category ───────────────────────────────
run_category_de() {
  local LABEL="$1"
  local TUMOR_MATRIX="$2"
  local NORMAL_MATRIX="$3"
  local OUT_DIR="${ANALYSIS_DIR}/${LABEL}"
  mkdir -p "${OUT_DIR}"

  # Merge
  if [[ ! -f "${OUT_DIR}/de_inputs/combined_counts.tsv" ]]; then
    echo "[prepare_inputs] ${LABEL}..."
    "${PYTHON_BIN}" "${SRC_DIR}/prepare_de_inputs.py" \
      --tumor_counts  "${TUMOR_MATRIX}" \
      --normal_counts "${NORMAL_MATRIX}" \
      --study_id      "${LABEL}" \
      --out_dir       "${OUT_DIR}/de_inputs"
  fi

  # DE
  if [[ ! -f "${OUT_DIR}/de_results/deg_long.tsv" ]]; then
    echo "[rna_de_prepare] ${LABEL}..."
    "${GENESET_BIN}" workflows rna_de_prepare \
      --modality            bulk \
      --counts_tsv          "${OUT_DIR}/de_inputs/combined_counts.tsv" \
      --sample_metadata_tsv "${OUT_DIR}/de_inputs/sample_metadata.tsv" \
      --sample_id_column    sample_id \
      --feature_id_column   gene_id \
      --group_column        condition \
      --comparison_mode     condition_a_vs_b \
      --condition_a         tumor \
      --condition_b         normal \
      --backend             r_limma_voom \
      --de_mode             modern \
      --out_dir             "${OUT_DIR}/de_results"
  fi

  # Gene sets
  if [[ ! -d "${OUT_DIR}/genesets" ]]; then
    echo "[rna_deg_multi] ${LABEL}..."
    "${GENESET_BIN}" convert rna_deg_multi \
      --deg_tsv           "${OUT_DIR}/de_results/deg_long.tsv" \
      --comparison_column comparison_id \
      --out_dir           "${OUT_DIR}/genesets" \
      --organism          human \
      --genome_build      hg38 \
      --padj_max          0.05 \
      --min_abs_logfc     1.0 \
      --select            top_k \
      --top_k             100
  fi

  echo "[done] ${LABEL}"
}

run_category_de "KF-BLOOD-vs-normal" "${BLOOD_TUMOR}" "${GTEX_BLOOD}"
run_category_de "KF-SOLID-vs-normal" "${SOLID_TUMOR}" "${GTEX_SOLID}"

# ── Step E: Blood vs Solid (internal contrast) ───────────────────────────────
# No external normal needed — compares the two cancer categories directly
# Labels both as "tumor" with different conditions: blood_cancer vs solid_cancer
BVS_DIR="${ANALYSIS_DIR}/KF-BLOOD-vs-SOLID"
mkdir -p "${BVS_DIR}"

if [[ ! -f "${BVS_DIR}/de_inputs/combined_counts.tsv" ]]; then
  echo "[prepare_inputs] KF-BLOOD-vs-SOLID (cancer category contrast)..."
  # For this comparison: blood cancer = "tumor", solid cancer = "normal" (label only)
  "${PYTHON_BIN}" "${SRC_DIR}/prepare_de_inputs.py" \
    --tumor_counts  "${BLOOD_TUMOR}" \
    --normal_counts "${SOLID_TUMOR}" \
    --study_id      "KF-BLOOD-vs-SOLID" \
    --out_dir       "${BVS_DIR}/de_inputs"
fi

if [[ ! -f "${BVS_DIR}/de_results/deg_long.tsv" ]]; then
  echo "[rna_de_prepare] KF-BLOOD-vs-SOLID..."
  "${GENESET_BIN}" workflows rna_de_prepare \
    --modality            bulk \
    --counts_tsv          "${BVS_DIR}/de_inputs/combined_counts.tsv" \
    --sample_metadata_tsv "${BVS_DIR}/de_inputs/sample_metadata.tsv" \
    --sample_id_column    sample_id \
    --feature_id_column   gene_id \
    --group_column        condition \
    --comparison_mode     condition_a_vs_b \
    --condition_a         tumor \
    --condition_b         normal \
    --backend             r_limma_voom \
    --de_mode             modern \
    --out_dir             "${BVS_DIR}/de_results"
fi

if [[ ! -d "${BVS_DIR}/genesets" ]]; then
  "${GENESET_BIN}" convert rna_deg_multi \
    --deg_tsv           "${BVS_DIR}/de_results/deg_long.tsv" \
    --comparison_column comparison_id \
    --out_dir           "${BVS_DIR}/genesets" \
    --organism          human \
    --genome_build      hg38 \
    --padj_max          0.05 \
    --min_abs_logfc     1.0 \
    --select            top_k \
    --top_k             100
fi

echo "ALL CATEGORY ANALYSES DONE: $(date)"
