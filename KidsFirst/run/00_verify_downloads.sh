#!/usr/bin/env bash
# Run interactively on login node BEFORE submitting sbatch_01_de_only.sh
# Usage: bash KidsFirst_DE_Analysis/run/00_verify_downloads.sh
#
# Checks:
#   1. KidsFirst RSEM files (rsem_files/ directory per study)
#   2. KidsFirst manifests (rsem_manifest.tsv per study)
#   3. GTEx v10 GCT files
#   4. geneset-extractors binary (from dig-gene-set-extractors git repo)
#   5. R + limma (required by rna_de_prepare)

set -uo pipefail

PROJECT_DIR="/path/to/your/project"
GTEX_DIR="${PROJECT_DIR}/inputs/GTEx/v10"
DIG_DIR="/path/to/dig-gene-set-extractors"
GENESET_BIN="${DIG_DIR}/.venv/bin/geneset-extractors"

PASS=0; FAIL=0

_pass() { echo "[PASS] $1"; ((PASS++)); }
_fail() { echo "[FAIL] $1"; ((FAIL++)); }
_warn() { echo "[WARN] $1"; }

# ── Check RSEM directory ─────────────────────────────────────────────────────
check_rsem_dir() {
  local label="$1" dir="$2" min_n="$3"
  if [[ ! -d "$dir" ]]; then
    _fail "${label}: directory missing — ${dir}"; return
  fi
  local n
  n=$(find "$dir" -name "*.rsem.genes.results.gz" -not -empty 2>/dev/null | wc -l)
  if [[ "$n" -lt "$min_n" ]]; then
    _fail "${label}: expected >=${min_n} .rsem.genes.results.gz, found ${n}"
  else
    local sz; sz=$(du -sh "$dir" 2>/dev/null | cut -f1)
    _pass "${label}: ${n} RSEM files (${sz})"
  fi
}

# ── Check file exists and is large enough ────────────────────────────────────
check_file() {
  local label="$1" file="$2" min_bytes="${3:-100000}"
  if [[ ! -f "$file" ]]; then
    _fail "${label}: file missing — ${file}"; return
  fi
  local sz; sz=$(wc -c < "$file")
  if [[ "$sz" -lt "$min_bytes" ]]; then
    _fail "${label}: too small (${sz} bytes, expected >=${min_bytes}) — ${file}"
  else
    local hsz; hsz=$(du -sh "$file" 2>/dev/null | cut -f1)
    _pass "${label}: ${hsz}"
  fi
}

echo "================================================================"
echo " KidsFirst DE Analysis — Pre-flight verification"
echo " Project: ${PROJECT_DIR}"
echo "================================================================"
echo ""

# ── 1. KidsFirst RSEM files ──────────────────────────────────────────────────
echo "--- 1. KidsFirst RSEM files ---"
check_rsem_dir "KF-TALL (T-ALL)"          "${PROJECT_DIR}/KidsFirst_KF_TALL/outputs/rsem_files"   500
check_rsem_dir "KF-NBL  (Neuroblastoma)"  "${PROJECT_DIR}/KidsFirst_KF_NBL/outputs/rsem_files"    100
check_rsem_dir "KF-ESGR (Ewing Sarcoma)"  "${PROJECT_DIR}/KidsFirst_KF_ESGR/outputs/rsem_files"    50
check_rsem_dir "KF-MMC  (AML)"            "${PROJECT_DIR}/KidsFirst_KF_MMC/outputs/rsem_files"     30
check_rsem_dir "KF-T21  (Down syndrome)"  "${PROJECT_DIR}/KidsFirst_KF_CHDALL/outputs/rsem_files" 100

# ── 2. KidsFirst manifests ───────────────────────────────────────────────────
echo ""
echo "--- 2. KidsFirst manifests (rsem_manifest.tsv) ---"
check_file "KF-TALL manifest" "${PROJECT_DIR}/KidsFirst_KF_TALL/config/rsem_manifest.tsv"   1000
check_file "KF-NBL  manifest" "${PROJECT_DIR}/KidsFirst_KF_NBL/config/rsem_manifest.tsv"    1000
check_file "KF-ESGR manifest" "${PROJECT_DIR}/KidsFirst_KF_ESGR/config/rsem_manifest.tsv"   500
check_file "KF-MMC  manifest" "${PROJECT_DIR}/KidsFirst_KF_MMC/config/rsem_manifest.tsv"    500
check_file "KF-T21  manifest" "${PROJECT_DIR}/KidsFirst_KF_CHDALL/config/rsem_manifest.tsv" 500

# ── 3. GTEx v10 files ────────────────────────────────────────────────────────
echo ""
echo "--- 3. GTEx v10 files ---"
check_file "GTEx whole_blood     (.gct.gz)" "${GTEX_DIR}/gene_reads_v10_whole_blood.gct.gz"     25000000
check_file "GTEx adrenal_gland   (.gct.gz)" "${GTEX_DIR}/gene_reads_v10_adrenal_gland.gct.gz"   5000000
check_file "GTEx muscle_skeletal (.gct.gz)" "${GTEX_DIR}/gene_reads_v10_muscle_skeletal.gct.gz" 20000000
check_file "GTEx brain_cortex    (.gct.gz)" "${GTEX_DIR}/gene_reads_v10_brain_cortex.gct.gz"    5000000
check_file "GTEx SampleAttributesDS (.txt)" \
  "${GTEX_DIR}/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt" 1000000

# ── 4. geneset-extractors binary ─────────────────────────────────────────────
echo ""
echo "--- 4. geneset-extractors (dig-gene-set-extractors git repo) ---"
echo "    Note: this is the EXTERNAL TOOL repo — do not modify it"
if [[ ! -d "$DIG_DIR" ]]; then
  _fail "dig-gene-set-extractors repo not found: ${DIG_DIR}"
elif [[ ! -x "$GENESET_BIN" ]]; then
  _fail "geneset-extractors binary missing or not executable: ${GENESET_BIN}"
  echo "      Fix: cd ${DIG_DIR} && python -m venv .venv && .venv/bin/pip install -e ."
else
  local_ver=$("$GENESET_BIN" --version 2>/dev/null || echo "version unknown")
  _pass "geneset-extractors: ${local_ver} (${GENESET_BIN})"
fi

# ── 5. R + limma ─────────────────────────────────────────────────────────────
echo ""
echo "--- 5. R and limma/edgeR ---"
if ! command -v Rscript &>/dev/null; then
  _fail "Rscript not in PATH — needed for rna_de_prepare --backend r_limma_voom"
  echo "      Fix: source /programs/biogrids.shrc && export PYTHON_X=3.9.16 before submission"
else
  R_VER=$(Rscript --version 2>&1 | head -1)
  _pass "Rscript: ${R_VER}"
  LIMMA_OK=$(Rscript -e 'if(requireNamespace("limma", quietly=TRUE)) cat("yes") else cat("no")' 2>/dev/null)
  EDGER_OK=$(Rscript -e 'if(requireNamespace("edgeR", quietly=TRUE)) cat("yes") else cat("no")' 2>/dev/null)
  if [[ "$LIMMA_OK" == "yes" ]]; then _pass "R limma package"; else _fail "R limma not installed"; fi
  if [[ "$EDGER_OK" == "yes" ]]; then _pass "R edgeR package"; else _fail "R edgeR not installed"; fi
fi

# ── 6. Python scripts (our analysis code) ────────────────────────────────────
echo ""
echo "--- 6. KidsFirst_DE_Analysis scripts (our code) ---"
echo "    Note: these are in KidsFirst_DE_Analysis/ — NOT in the git repo"
SCRIPT_SRC="${PROJECT_DIR}/KidsFirst_DE_Analysis/src"
for script in build_rsem_matrix.py extract_gtex_counts.py prepare_de_inputs.py \
              merge_study_matrices.py extract_immune_genesets.py \
              summarize_de_natural_sizes.py; do
  check_file "${script}" "${SCRIPT_SRC}/${script}" 100
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo " RESULT: ${PASS} passed, ${FAIL} failed"
echo "================================================================"
if [[ "$FAIL" -eq 0 ]]; then
  echo " Ready to submit: sbatch KidsFirst_DE_Analysis/run/sbatch_01_de_only.sh"
else
  echo " Fix ${FAIL} failure(s) before submitting jobs."
  exit 1
fi
