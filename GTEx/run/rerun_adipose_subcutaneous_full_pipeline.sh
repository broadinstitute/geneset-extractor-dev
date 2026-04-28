#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GTEX_ROOT="${REPO_ROOT}/geneset-extractor-dev/GTEx"

PYTHON_BIN="${PYTHON_BIN:-/home/ryank/software/miniconda3/envs/work/bin/python}"
RSCRIPT_BIN="${RSCRIPT_BIN:-/home/ryank/software/miniconda3/envs/work/bin/Rscript}"

TISSUE_ID="${TISSUE_ID:-adipose_subcutaneous}"
TISSUE_LABEL="${TISSUE_LABEL:-Adipose - Subcutaneous}"

COUNTS_GCT="${COUNTS_GCT:-${REPO_ROOT}/inputs/GTEx/v10/gene_reads_v10_adipose_subcutaneous.gct.gz}"
SAMPLE_METADATA_TSV="${SAMPLE_METADATA_TSV:-${REPO_ROOT}/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SampleAttributesDS.txt}"
SUBJECT_METADATA_TSV="${SUBJECT_METADATA_TSV:-${REPO_ROOT}/inputs/GTEx/v10/GTEx_Analysis_v10_Annotations_SubjectPhenotypesDS.txt}"
GTF_PATH="${GTF_PATH:-${REPO_ROOT}/inputs/GTEx/v10/gencode.v26.annotation.gtf.gz}"

GENESET_TISSUE_ROOT="${GENESET_TISSUE_ROOT:-${GTEX_ROOT}/outputs/genesets/${TISSUE_ID}}"
PREPARED_DIR="${PREPARED_DIR:-${GENESET_TISSUE_ROOT}/prepared}"
COMPARISON_MODEL_RUN_ROOT="${COMPARISON_MODEL_RUN_ROOT:-${GENESET_TISSUE_ROOT}/models}"
TISSUE_MODEL_RUN_ROOT="${TISSUE_MODEL_RUN_ROOT:-${GENESET_TISSUE_ROOT}/tissue_models}"
COMPARISON_IDENTICAL_OUT_DIR="${COMPARISON_IDENTICAL_OUT_DIR:-${GENESET_TISSUE_ROOT}/identical_model_check}"
TISSUE_IDENTICAL_OUT_DIR="${TISSUE_IDENTICAL_OUT_DIR:-${GENESET_TISSUE_ROOT}/tissue_identical_model_check}"

PIGEAN_EAGGL_OUT_DIR="${PIGEAN_EAGGL_OUT_DIR:-${GTEX_ROOT}/outputs/pigean_eaggl}"

cat <<EOF
Running GTEx adipose subcutaneous full rerun pipeline with:
  PYTHON_BIN=${PYTHON_BIN}
  RSCRIPT_BIN=${RSCRIPT_BIN}
  TISSUE_ID=${TISSUE_ID}
  PREPARED_DIR=${PREPARED_DIR}
  COMPARISON_MODEL_RUN_ROOT=${COMPARISON_MODEL_RUN_ROOT}
  TISSUE_MODEL_RUN_ROOT=${TISSUE_MODEL_RUN_ROOT}
  COMPARISON_IDENTICAL_OUT_DIR=${COMPARISON_IDENTICAL_OUT_DIR}
  TISSUE_IDENTICAL_OUT_DIR=${TISSUE_IDENTICAL_OUT_DIR}
  PIGEAN_EAGGL_OUT_DIR=${PIGEAN_EAGGL_OUT_DIR}
EOF

bash "${GTEX_ROOT}/run/prepare_gtex_tissue_inputs.sh" \
  --python_bin "${PYTHON_BIN}" \
  --counts_gct "${COUNTS_GCT}" \
  --sample_metadata_tsv "${SAMPLE_METADATA_TSV}" \
  --subject_metadata_tsv "${SUBJECT_METADATA_TSV}" \
  --tissue_label "${TISSUE_LABEL}" \
  --out_dir "${PREPARED_DIR}"

bash "${GTEX_ROOT}/run/run_all_gtex_models.sh" \
  --prepared_dir "${PREPARED_DIR}" \
  --run_root "${COMPARISON_MODEL_RUN_ROOT}" \
  --python_bin "${PYTHON_BIN}" \
  --gtf "${GTF_PATH}"

bash "${GTEX_ROOT}/run/run_gtex_tissue_gmt.sh" \
  --python_bin "${PYTHON_BIN}" \
  --tissue_id "${TISSUE_ID}" \
  --prepared_dir "${PREPARED_DIR}" \
  --run_root "${TISSUE_MODEL_RUN_ROOT}" \
  --rscript_bin "${RSCRIPT_BIN}" \
  --model_ids all \
  --gtf "${GTF_PATH}"

bash "${GTEX_ROOT}/run/check_identical_gtex_models.sh" \
  --python_bin "${PYTHON_BIN}" \
  --models_root "${COMPARISON_MODEL_RUN_ROOT}" \
  --out_dir "${COMPARISON_IDENTICAL_OUT_DIR}"

bash "${GTEX_ROOT}/run/check_identical_gtex_models.sh" \
  --python_bin "${PYTHON_BIN}" \
  --models_root "${TISSUE_MODEL_RUN_ROOT}" \
  --out_dir "${TISSUE_IDENTICAL_OUT_DIR}"

PYTHON_BIN="${PYTHON_BIN}" \
bash "${GTEX_ROOT}/run/run_pigean_eaggl.sh" \
  --outputs_root "${GTEX_ROOT}/outputs/genesets" \
  --out_dir "${PIGEAN_EAGGL_OUT_DIR}" \
  --tissues "${TISSUE_ID}"

PYTHON_BIN="${PYTHON_BIN}" \
bash "${GTEX_ROOT}/run/summarize_pigean_eaggl_results.sh" \
  --run_root "${PIGEAN_EAGGL_OUT_DIR}" \
  --tissue "${TISSUE_ID}" \
  --model_group models

PYTHON_BIN="${PYTHON_BIN}" \
bash "${GTEX_ROOT}/run/summarize_pigean_eaggl_results.sh" \
  --run_root "${PIGEAN_EAGGL_OUT_DIR}" \
  --tissue "${TISSUE_ID}" \
  --model_group tissue_models
