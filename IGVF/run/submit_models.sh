#!/usr/bin/env bash
set -euo pipefail

library_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
workspace_root=$(cd -- "${library_root}/../.." && pwd -P)
dig_root=${DIG_ROOT:-"${workspace_root}/dig-gene-set-extractors"}
inputs_root=${1:?usage: submit_models.sh INPUTS_ROOT OUTPUT_ROOT [ANALYSIS_SET_ID,...]}
output_root=${2:?usage: submit_models.sh INPUTS_ROOT OUTPUT_ROOT [ANALYSIS_SET_ID,...]}
requested=${3:-all}
config=${library_root}/config/analysis_set_list.tsv
python_bin=${PYTHON:-python3}

run_one() {
  local analysis_set_id=$1 dataset_id=$2 file_relpath=$3 sep=$4 term_column=$5 gene_symbol_column=$6 gene_id_column=$7 effect_column=$8 ratio_column=$9 score_column=${10} pvalue_column=${11} pvalue_max=${12} score_threshold=${13} top_k_per_direction=${14}
  local expression_tsv=${inputs_root}/${file_relpath}
  local workflow_out=${output_root}/genesets/${analysis_set_id}/models/PS1/workflow
  local extractor_out=${output_root}/genesets/${analysis_set_id}/models/PS1/extractor
  [[ -f "${expression_tsv}" ]] || { echo "missing declared input: ${expression_tsv}" >&2; return 1; }
  mkdir -p "${workflow_out}" "${extractor_out}"
  local command=("${python_bin}" -m geneset_extractors.cli workflows igvf_perturbseq --input_mode long_de --expression_tsv "${expression_tsv}" --out_dir "${workflow_out}" --organism human --genome_build hg38 --gmt_name gene_set_library_crisp.gmt --min_gmt_size 5 --sep "${sep}" --term_column "${term_column}" --gene_symbol_column "${gene_symbol_column}")
  [[ "${gene_id_column}" != "NA" ]] && command+=(--gene_id_column "${gene_id_column}")
  [[ "${effect_column}" != "NA" ]] && command+=(--effect_column "${effect_column}")
  [[ "${ratio_column}" != "NA" ]] && command+=(--ratio_column "${ratio_column}")
  [[ "${score_column}" != "NA" ]] && command+=(--score_column "${score_column}")
  [[ "${pvalue_column}" != "NA" ]] && command+=(--pvalue_column "${pvalue_column}")
  [[ "${pvalue_max}" != "NA" ]] && command+=(--pvalue_max "${pvalue_max}")
  [[ "${score_threshold}" != "NA" ]] && command+=(--score_threshold "${score_threshold}")
  [[ "${top_k_per_direction}" != "NA" ]] && command+=(--top_k_per_direction "${top_k_per_direction}")
  PYTHONPATH="${dig_root}/src${PYTHONPATH:+:${PYTHONPATH}}" "${command[@]}"
  PYTHONPATH="${dig_root}/src${PYTHONPATH:+:${PYTHONPATH}}" "${python_bin}" -m geneset_extractors.cli convert signed_term_gene --table_tsv "${workflow_out}/igvf_perturbseq_signed_term_gene.tsv" --out_dir "${extractor_out}" --organism human --genome_build hg38 --term_column term --term_prefix IGVF_Perturb_Seq --gene_id_column gene_id --gene_symbol_column gene_symbol --score_column score --sign_column sign --gmt_name_separator _ --gmt_signed_labels up_dn --gmt_min_genes 5 --gmt_require_symbol true --emit_small_gene_sets false
}

while IFS=$'\t' read -r analysis_set_id dataset_id file_relpath schema sep term_column gene_symbol_column gene_id_column effect_column ratio_column score_column pvalue_column pvalue_max score_threshold top_k_per_direction enabled; do
  [[ "${analysis_set_id}" == "analysis_set_id" || "${enabled}" != "true" ]] && continue
  [[ "${requested}" == all || ",${requested}," == *",${analysis_set_id},"* ]] || continue
  run_one "${analysis_set_id}" "${dataset_id}" "${file_relpath}" "${sep}" "${term_column}" "${gene_symbol_column}" "${gene_id_column}" "${effect_column}" "${ratio_column}" "${score_column}" "${pvalue_column}" "${pvalue_max}" "${score_threshold}" "${top_k_per_direction}"
done < "${config}"
