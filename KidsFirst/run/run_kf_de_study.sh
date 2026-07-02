#!/usr/bin/env bash
# Run the full DE + gene set pipeline for one KidsFirst study.
#
# Normal control source — two modes (mutually exclusive):
#   A) GTEx tissue:      --gtex_gct <path> --gtex_tissue <SMTSD value>
#   B) KidsFirst normal: --normal_study <study_folder_name>
#
# Outputs under: $project_dir/outputs/analysis/$study_id/
set -euo pipefail

# ── argument parsing ─────────────────────────────────────────────────────────
PROJECT_DIR=""
STUDY=""
GTEX_GCT=""
GTEX_TISSUE=""
NORMAL_STUDY=""   # e.g. KidsFirst_KF_CHDALL — use another KF study as normal
STUDY_ID=""
DIG_DIR=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --project_dir)   PROJECT_DIR="$2";   shift 2 ;;
    --study)         STUDY="$2";         shift 2 ;;
    --gtex_gct)      GTEX_GCT="$2";      shift 2 ;;
    --gtex_tissue)   GTEX_TISSUE="$2";   shift 2 ;;
    --normal_study)  NORMAL_STUDY="$2";  shift 2 ;;
    --study_id)      STUDY_ID="$2";      shift 2 ;;
    --dig_dir)       DIG_DIR="$2";       shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$PROJECT_DIR" || -z "$STUDY" || -z "$STUDY_ID" || -z "$DIG_DIR" ]] && \
  { echo "ERROR: --project_dir, --study, --study_id, --dig_dir are required" >&2; exit 1; }

USE_GTEX=false
USE_KF_NORMAL=false
if [[ -n "$GTEX_GCT" && -n "$GTEX_TISSUE" ]]; then
  USE_GTEX=true
elif [[ -n "$NORMAL_STUDY" ]]; then
  USE_KF_NORMAL=true
else
  echo "ERROR: provide either (--gtex_gct + --gtex_tissue) or --normal_study" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"
STUDY_DIR="${PROJECT_DIR}/${STUDY}"
GTEX_SAMPLE_ATTRS="${PROJECT_DIR}/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt"
OUT_DIR="${PROJECT_DIR}/outputs/analysis/${STUDY_ID}"
WORKERS="${SLURM_CPUS_PER_TASK:-4}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
GENESET_BIN="${GENESET_BIN:-geneset-extractors}"

echo "=============================="
echo "study_id:     ${STUDY_ID}"
if $USE_GTEX; then
  echo "normal:       GTEx ${GTEX_TISSUE}"
else
  echo "normal:       KidsFirst ${NORMAL_STUDY}"
fi
echo "out_dir:      ${OUT_DIR}"
echo "start:        $(date)"
echo "=============================="

mkdir -p "${OUT_DIR}"

# ── Step 1: Build tumor RSEM count matrix ────────────────────────────────────
RSEM_COUNTS="${OUT_DIR}/rsem_counts.tsv"
if [[ -f "${RSEM_COUNTS}" ]]; then
  echo "[Step 1] RSEM matrix exists, skipping"
else
  echo "[Step 1] Building tumor RSEM count matrix (${STUDY})..."
  "${PYTHON_BIN}" "${SRC_DIR}/build_rsem_matrix.py" \
    --rsem_dir     "${STUDY_DIR}/outputs/rsem_files" \
    --manifest_tsv "${STUDY_DIR}/config/rsem_manifest.tsv" \
    --out_tsv      "${RSEM_COUNTS}" \
    --workers      "${WORKERS}"
fi

# ── Step 2: Build normal count matrix ────────────────────────────────────────
NORMAL_COUNTS="${OUT_DIR}/normal_counts.tsv"
if [[ -f "${NORMAL_COUNTS}" ]]; then
  echo "[Step 2] Normal counts exist, skipping"
elif $USE_GTEX; then
  echo "[Step 2] Extracting GTEx counts for '${GTEX_TISSUE}'..."
  "${PYTHON_BIN}" "${SRC_DIR}/extract_gtex_counts.py" \
    --gct          "${PROJECT_DIR}/${GTEX_GCT}" \
    --sample_attrs "${GTEX_SAMPLE_ATTRS}" \
    --tissue       "${GTEX_TISSUE}" \
    --out_tsv      "${NORMAL_COUNTS}"
else
  echo "[Step 2] Building normal RSEM count matrix (${NORMAL_STUDY})..."
  NORMAL_DIR="${PROJECT_DIR}/${NORMAL_STUDY}"
  "${PYTHON_BIN}" "${SRC_DIR}/build_rsem_matrix.py" \
    --rsem_dir     "${NORMAL_DIR}/outputs/rsem_files" \
    --manifest_tsv "${NORMAL_DIR}/config/rsem_manifest.tsv" \
    --out_tsv      "${NORMAL_COUNTS}" \
    --workers      "${WORKERS}"
fi

# ── Step 3: Merge + create sample metadata ───────────────────────────────────
DE_INPUTS_DIR="${OUT_DIR}/de_inputs"
if [[ -f "${DE_INPUTS_DIR}/combined_counts.tsv" ]]; then
  echo "[Step 3] DE inputs exist, skipping"
else
  echo "[Step 3] Merging counts and creating sample metadata..."
  "${PYTHON_BIN}" "${SRC_DIR}/prepare_de_inputs.py" \
    --tumor_counts   "${RSEM_COUNTS}" \
    --normal_counts  "${NORMAL_COUNTS}" \
    --tumor_metadata "${STUDY_DIR}/config/sample_metadata.tsv" \
    --study_id       "${STUDY_ID}" \
    --out_dir        "${DE_INPUTS_DIR}"
fi

# ── Step 4: Differential expression (limma-voom) ─────────────────────────────
DE_OUT="${OUT_DIR}/de_results"
if [[ -f "${DE_OUT}/deg_long.tsv" ]]; then
  echo "[Step 4] DE results exist, skipping"
else
  echo "[Step 4] Running rna_de_prepare (limma-voom)..."
  "${GENESET_BIN}" workflows rna_de_prepare \
    --modality            bulk \
    --counts_tsv          "${DE_INPUTS_DIR}/combined_counts.tsv" \
    --sample_metadata_tsv "${DE_INPUTS_DIR}/sample_metadata.tsv" \
    --sample_id_column    sample_id \
    --feature_id_column   gene_id \
    --group_column        condition \
    --comparison_mode     condition_a_vs_b \
    --condition_a         tumor \
    --condition_b         normal \
    --backend             r_limma_voom \
    --de_mode             modern \
    --out_dir             "${DE_OUT}"
fi

# ── Step 5: Gene set extraction ───────────────────────────────────────────────
GENESET_OUT="${OUT_DIR}/genesets"
if [[ -d "${GENESET_OUT}" ]]; then
  echo "[Step 5] Gene sets exist, skipping"
else
  echo "[Step 5] Extracting gene sets (padj<0.05, |logFC|>=1, top_k=100)..."
  "${GENESET_BIN}" convert rna_deg_multi \
    --deg_tsv           "${DE_OUT}/deg_long.tsv" \
    --comparison_column comparison_id \
    --out_dir           "${GENESET_OUT}" \
    --organism          human \
    --genome_build      hg38 \
    --padj_max          0.05 \
    --min_abs_logfc     1.0 \
    --select            top_k \
    --top_k             100
fi

echo "=============================="
echo "DONE: ${STUDY_ID}"
echo "end: $(date)"
echo "Outputs: ${OUT_DIR}"
echo "=============================="
