# analyze_one_missing_legacy_set v1

This script traces one gene set that appears in the legacy GTEx aging GMT but is absent from the `harmonizome_legacy_gtex_reproduction_v1` GMT.

The default set is `GTEx_Blood_20-29_vs_30-39_Up`, chosen because the comparison is represented in the reproduction input but the reproduced DE result has no adjusted-significant genes in the missing direction.

Outputs are written under `outputs/one_missing_legacy_set_analysis_v1/`:

- `one_missing_legacy_set_analysis.v1.md`
- `selected_missing_set_summary.v1.tsv`
- `legacy_gene_status_in_reproduction.v1.tsv`
- `legacy_genes_in_reproduction_by_adj_p_val.v1.tsv`
- `top_reproduction_genes_by_adj_p_val.v1.tsv`
- `top_reproduction_genes_in_missing_direction.v1.tsv`
- `analyze_one_missing_legacy_set.v1.log`
