#!/bin/bash
#SBATCH --job-name=KF_DE_analysis
#SBATCH --output=KidsFirst_DE_Analysis/logs/kf_de_%j.out
#SBATCH --error=KidsFirst_DE_Analysis/logs/kf_de_%j.err
#SBATCH --time=12:00:00
#SBATCH --mem=96G
#SBATCH --cpus-per-task=8
#SBATCH --partition=bch-compute
#SBATCH --mail-type=BEGIN,END,FAIL

source /programs/biogrids.shrc
export PYTHON_X=3.9.16

set -euo pipefail

PROJECT_DIR="/path/to/your/project"
DIG_DIR="/path/to/dig-gene-set-extractors"
SCRIPT_DIR="${PROJECT_DIR}/KidsFirst_DE_Analysis/run"

mkdir -p "${PROJECT_DIR}/KidsFirst_DE_Analysis/logs"

export PYTHON_BIN="python3"
export GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

echo "start: $(date)"
echo "project_dir: ${PROJECT_DIR}"

# ── KF-TALL vs KF-CHDALL (소아 T21 혈액, primary) ───────────────────────────
# KF-CHDALL은 같은 KidsFirst RSEM 파이프라인 → batch 최소화
# T21 blood baseline을 통제하여 T-ALL 특이 신호를 더 clean하게 추출
bash "${SCRIPT_DIR}/run_kf_de_study.sh" \
  --project_dir  "${PROJECT_DIR}" \
  --study        KidsFirst_KF_TALL \
  --gtex_gct     "" \
  --gtex_tissue  "" \
  --normal_study KidsFirst_KF_CHDALL \
  --study_id     KF-TALL-vs-T21 \
  --dig_dir      "${DIG_DIR}"

# ── KF-TALL vs GTEx Whole Blood (성인 정상혈액, secondary/validation) ────────
bash "${SCRIPT_DIR}/run_kf_de_study.sh" \
  --project_dir  "${PROJECT_DIR}" \
  --study        KidsFirst_KF_TALL \
  --gtex_gct     "inputs/GTEx/v10/gene_reads_v10_whole_blood.gct.gz" \
  --gtex_tissue  "Whole Blood" \
  --study_id     KF-TALL-vs-GTEx \
  --dig_dir      "${DIG_DIR}"

# ── KF-NBL vs GTEx Adrenal Gland ─────────────────────────────────────────────
bash "${SCRIPT_DIR}/run_kf_de_study.sh" \
  --project_dir  "${PROJECT_DIR}" \
  --study        KidsFirst_KF_NBL \
  --gtex_gct     "inputs/GTEx/v10/gene_reads_v10_adrenal_gland.gct.gz" \
  --gtex_tissue  "Adrenal Gland" \
  --study_id     KF-NBL \
  --dig_dir      "${DIG_DIR}"

# ── KF-ESGR vs GTEx Muscle - Skeletal ────────────────────────────────────────
bash "${SCRIPT_DIR}/run_kf_de_study.sh" \
  --project_dir  "${PROJECT_DIR}" \
  --study        KidsFirst_KF_ESGR \
  --gtex_gct     "inputs/GTEx/v10/gene_reads_v10_muscle_skeletal.gct.gz" \
  --gtex_tissue  "Muscle - Skeletal" \
  --study_id     KF-ESGR \
  --dig_dir      "${DIG_DIR}"

# ── KF-MMC (AML) vs GTEx Whole Blood ─────────────────────────────────────────
bash "${SCRIPT_DIR}/run_kf_de_study.sh" \
  --project_dir  "${PROJECT_DIR}" \
  --study        KidsFirst_KF_MMC \
  --gtex_gct     "inputs/GTEx/v10/gene_reads_v10_whole_blood.gct.gz" \
  --gtex_tissue  "Whole Blood" \
  --study_id     KF-MMC \
  --dig_dir      "${DIG_DIR}"

echo "ALL DONE: $(date)"
