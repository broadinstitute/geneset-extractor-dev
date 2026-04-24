#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "${repo_root}/src/run_harmonizome_legacy_gtex_reproduction.v2.py" \
  --output_dir "${repo_root}/outputs/harmonizome_legacy_gtex_reproduction_v1" \
  --counts_gct_gz_path "${repo_root}/outputs/gtex_no_harmonizome_analysis_v1/downloads/GTEx_Analysis_2017-06-05_v8_RNASeQCv1.1.9_gene_reads.gct.gz" \
  --sample_attributes_path "${repo_root}/outputs/gtex_no_harmonizome_analysis_v1/downloads/GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt" \
  --subject_phenotypes_path "${repo_root}/outputs/gtex_no_harmonizome_analysis_v1/downloads/GTEx_Analysis_v8_Annotations_SubjectPhenotypesDS.txt" \
  --mapping_path "${repo_root}/pigean/bundles/model_small-2026.02.22/data/portal_gencode.gene.map" \
  --next_pending_tissue \
  "$@"
