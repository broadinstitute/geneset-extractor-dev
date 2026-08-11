#!/usr/bin/env bash
set -euo pipefail

library_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
workspace_root=$(cd -- "${library_root}/../.." && pwd -P)
mode=${1:-full}
case "${mode}" in
  --smoke)
    smoke_out=${library_root}/outputs/smoke
    mkdir -p "${smoke_out}/genesets/SMOKE/models/PS1/workflow" "${smoke_out}/genesets/SMOKE/models/PS1/extractor"
    PYTHONPATH="${workspace_root}/dig-gene-set-extractors/src${PYTHONPATH:+:${PYTHONPATH}}" "${PYTHON:-python3}" -m geneset_extractors.cli workflows igvf_perturbseq --input_mode long_de --expression_tsv "${library_root}/tests/fixtures/smoke_long_de.tsv" --out_dir "${smoke_out}/genesets/SMOKE/models/PS1/workflow" --term_column perturbation --gene_symbol_column gene_symbol --gene_id_column gene_id --effect_column log2fc --pvalue_column p_value --pvalue_max 0.05 --top_k_per_direction 2 --min_gmt_size 2
    PYTHONPATH="${workspace_root}/dig-gene-set-extractors/src${PYTHONPATH:+:${PYTHONPATH}}" "${PYTHON:-python3}" -m geneset_extractors.cli convert signed_term_gene --table_tsv "${smoke_out}/genesets/SMOKE/models/PS1/workflow/igvf_perturbseq_signed_term_gene.tsv" --out_dir "${smoke_out}/genesets/SMOKE/models/PS1/extractor" --organism human --genome_build hg38 --term_column term --term_prefix IGVF_Perturb_Seq --gene_id_column gene_id --gene_symbol_column gene_symbol --score_column score --sign_column sign --gmt_name_separator _ --gmt_signed_labels up_dn --gmt_min_genes 2 --gmt_require_symbol true --emit_small_gene_sets false
    ;;
  full)
    inputs_root=${IGVF_INPUTS_ROOT:-"${workspace_root}/inputs/IGVF"}
    bash "${library_root}/reproduction/download_inputs.sh" "${inputs_root}"
    bash "${library_root}/run/submit_models.sh" "${inputs_root}" "${library_root}/outputs/full"
    ;;
  *) echo 'usage: reproduce.sh [--smoke|full]' >&2; exit 2 ;;
esac
