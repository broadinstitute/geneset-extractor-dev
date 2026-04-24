# analyze_shared_low_overlap_gene_set v1

This script traces a gene set that appears in both the legacy GTEx aging GMT and the `harmonizome_legacy_gtex_reproduction_v1` GMT but has minimal overlap.

The default set is `GTEx_Skin_20-29_vs_60-69_Up`, which has 250 legacy genes, 250 reproduced genes, and zero shared genes.

Outputs are written under `outputs/shared_low_overlap_gene_set_analysis_v1/`:

- `shared_low_overlap_gene_set_analysis.v1.md`
- `selected_low_overlap_set_summary.v1.tsv`
- `legacy_gene_status_in_reproduction.v1.tsv`
- `reproduced_gene_status.v1.tsv`
- `legacy_exclusion_reason_summary.v1.tsv`
- `reproduced_inclusion_reason_summary.v1.tsv`
- `top_reproduction_de_genes.v1.tsv`
- `top_legacy_genes_by_reproduction_adj_p_val.v1.tsv`
- `top_reproduced_only_genes.v1.tsv`
- `shared_genes.v1.tsv`
- `legacy_only_genes.v1.tsv`
- `reproduced_only_genes.v1.tsv`
- `analyze_shared_low_overlap_gene_set.v1.log`
