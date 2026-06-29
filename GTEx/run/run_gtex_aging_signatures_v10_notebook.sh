#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
JUPYTER_BIN="${JUPYTER_BIN:-jupyter}"
RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"

COUNTS_GCT="${COUNTS_GCT:-${REPO_ROOT}/inputs/GTEx/v10/GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz}"
SAMPLE_METADATA_TSV="${SAMPLE_METADATA_TSV:-${REPO_ROOT}/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt}"
SUBJECT_METADATA_TSV="${SUBJECT_METADATA_TSV:-${REPO_ROOT}/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt}"
GTF_PATH="${GTF_PATH:-${REPO_ROOT}/inputs/GTEx/v10/gencode.v39.annotation.gtf.gz}"
SOURCE_NOTEBOOK="${SOURCE_NOTEBOOK:-${REPO_ROOT}/GTExAgingSignatures.ipynb}"
REFERENCE_GMT="${REFERENCE_GMT:-${REPO_ROOT}/GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/gtex_outputs/gtex_aging_signatures_v10_notebook}"

export RSCRIPT_BIN

PATCHED_NOTEBOOK="${OUT_DIR}/GTExAgingSignatures.v10.generated.ipynb"
EXEC_NOTEBOOK="${OUT_DIR}/GTExAgingSignatures.v10.executed.ipynb"
COMPARE_DIR="${OUT_DIR}/comparison_to_v8"
LOG_PATH="${OUT_DIR}/run.log"
COMMANDS_MD="${OUT_DIR}/commands.md"

mkdir -p "${OUT_DIR}" "${COMPARE_DIR}"

{
  echo "# Commands"
  echo
  echo '```bash'
  printf '%q ' "$0" "$@"
  echo
  echo '```'
  echo
  echo "- counts_gct: \`${COUNTS_GCT}\`"
  echo "- sample_metadata_tsv: \`${SAMPLE_METADATA_TSV}\`"
  echo "- subject_metadata_tsv: \`${SUBJECT_METADATA_TSV}\`"
  echo "- gtf: \`${GTF_PATH}\`"
  echo "- source_notebook: \`${SOURCE_NOTEBOOK}\`"
  echo "- reference_gmt: \`${REFERENCE_GMT}\`"
  echo "- rscript_bin: \`${RSCRIPT_BIN}\`"
  echo "- out_dir: \`${OUT_DIR}\`"
} > "${COMMANDS_MD}"

{
  echo "[run_gtex_aging_signatures_v10_notebook] start"
  echo "source_notebook=${SOURCE_NOTEBOOK}"
  echo "counts_gct=${COUNTS_GCT}"
  echo "sample_metadata_tsv=${SAMPLE_METADATA_TSV}"
  echo "subject_metadata_tsv=${SUBJECT_METADATA_TSV}"
  echo "gtf=${GTF_PATH}"
  echo "reference_gmt=${REFERENCE_GMT}"
  echo "rscript_bin=${RSCRIPT_BIN}"
  echo "out_dir=${OUT_DIR}"
} > "${LOG_PATH}"

"${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/GTEx/src/prepare_gtex_aging_signatures_v10_notebook.py" \
  --source_notebook "${SOURCE_NOTEBOOK}" \
  --counts_gct "${COUNTS_GCT}" \
  --sample_metadata_tsv "${SAMPLE_METADATA_TSV}" \
  --subject_metadata_tsv "${SUBJECT_METADATA_TSV}" \
  --gtf "${GTF_PATH}" \
  --output_dir "${OUT_DIR}" \
  --output_notebook "${PATCHED_NOTEBOOK}" >> "${LOG_PATH}" 2>&1

cp "${PATCHED_NOTEBOOK}" "${EXEC_NOTEBOOK}"

"${JUPYTER_BIN}" nbconvert \
  --to notebook \
  --execute \
  --inplace \
  "${EXEC_NOTEBOOK}" >> "${LOG_PATH}" 2>&1

"${PYTHON_BIN}" "${REPO_ROOT}/geneset-extractor-dev/GTEx/src/compare_gtex_aging_gmt_to_v8.py" \
  --up_gmt "${OUT_DIR}/downloads/gene_set_library_up_crisp.gmt" \
  --down_gmt "${OUT_DIR}/downloads/gene_set_library_dn_crisp.gmt" \
  --reference_gmt "${REFERENCE_GMT}" \
  --out_dir "${COMPARE_DIR}" >> "${LOG_PATH}" 2>&1

echo "[run_gtex_aging_signatures_v10_notebook] complete" >> "${LOG_PATH}"
