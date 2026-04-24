# Shared Low-Overlap Gene Set Analysis v1

## Take-Home Summary

The selected set is `GTEx_Skin_20-29_vs_60-69_Up`. It appears in both GMT files, but the two versions have low overlap with 16 shared genes: legacy has 250 genes, the reproduction has 250 genes, shared genes=16, Jaccard=0.033058.
The comparison itself is represented in the reproduction and was run with 149 `20-29` samples versus 149 `60-69` samples.
The reproduced set consists of the top 250 genes with `adj_p_val < 0.05` and positive logFC among 691 significant positive genes in the reproduced DE table.
The legacy genes are mostly excluded from the reproduced set because 16 legacy genes satisfy the reproduced inclusion rule for this set; 92 of 250 legacy genes are present in the reproduced DEG table, 89 have positive reproduced logFC, 34 are adjusted-significant, and 16 would rank into the reproduced top 250.
The best same-size candidate in this sweep used score=adj_p_val <= 0.25, abs_logfc_min=0.5, top_k=250; it recovered 44 of 250 legacy genes (Jaccard=0.096491). Recovering all same-direction legacy genes present in the reproduced DEG table would require pvalue <= 0.81945, which admits 10415 same-direction genes before any top-k cap.

## Identifier Diagnostics

- processed matrix rows: 49877
- unique processed matrix gene symbols: 49877
- duplicate processed matrix gene-symbol rows: 0
- numeric gene symbols in processed matrix: 0
- processed matrix identifiers are valid for this comparison.

## Membership Examples

- first 10 legacy genes: DUXAP8, CXCL10, EYA4, BCAP31P1, BCAP31P2, GRIK4, LHFPL4, CXCL9, RPS14P1, GPR149
- first 10 reproduced genes: STAB2, PCDHB2, KHDC1-AS1, B2M, DZIP1L, SCN2A, TSNAX, PEF1-AS1, ZC2HC1A, ZNF833P

## Legacy Gene Exclusion Reasons In The Reproduction

- absent_from_reproduced_deg_table: 158
- present_same_direction_but_not_adj_p_significant: 55
- present_significant_same_direction_but_ranked_below_top_250: 18
- present_and_would_have_been_in_reproduced_set: 16
- present_but_wrong_logfc_direction: 3

## Example Legacy Genes And Why They Are Excluded

- DUXAP8: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- CXCL10: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- EYA4: present_significant_same_direction_but_ranked_below_top_250, logFC=0.979935445888106, adj_p_val=0.0262878903143384
- BCAP31P1: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- BCAP31P2: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- GRIK4: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- LHFPL4: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- CXCL9: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- RPS14P1: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA
- GPR149: absent_from_reproduced_deg_table, logFC=NA, adj_p_val=NA

## Example Reproduced Genes And Why They Are Included

- STAB2: rank=1, logFC=1.17284, adj_p_val=6.44076e-06
- PCDHB2: rank=2, logFC=0.612104, adj_p_val=1.30911e-05
- KHDC1-AS1: rank=3, logFC=0.394338, adj_p_val=4.04172e-05
- B2M: rank=4, logFC=0.276226, adj_p_val=9.87582e-05
- DZIP1L: rank=5, logFC=0.352425, adj_p_val=0.000151693
- SCN2A: rank=6, logFC=0.901925, adj_p_val=0.000151693
- TSNAX: rank=7, logFC=0.274782, adj_p_val=0.000151693
- PEF1-AS1: rank=8, logFC=0.553966, adj_p_val=0.000197895
- ZC2HC1A: rank=9, logFC=0.330947, adj_p_val=0.000209846
- ZNF833P: rank=10, logFC=0.367559, adj_p_val=0.000228392

## Threshold Sweep

The sweep varied score metric, score cutoff, minimum absolute logFC, and top-k cap using the reproduced DEG table for the same comparison and direction.
These thresholds can only recover legacy genes that are present in the reproduced DEG table with the same logFC direction; they cannot recover genes absent from the reproduced DEG table.

Top threshold configurations by Jaccard against the legacy set:

- score=adj_p_val <= 0.1, abs_logfc_min=0.5, top_k=250: candidate_genes=144, shared=38, Jaccard=0.106742, legacy_recall=0.152, precision=0.264
- score=adj_p_val <= 0.1, abs_logfc_min=0.5, top_k=500: candidate_genes=144, shared=38, Jaccard=0.106742, legacy_recall=0.152, precision=0.264
- score=adj_p_val <= 0.1, abs_logfc_min=0.5, top_k=1000: candidate_genes=144, shared=38, Jaccard=0.106742, legacy_recall=0.152, precision=0.264
- score=adj_p_val <= 0.1, abs_logfc_min=0.5, top_k=2500: candidate_genes=144, shared=38, Jaccard=0.106742, legacy_recall=0.152, precision=0.264
- score=adj_p_val <= 0.1, abs_logfc_min=0.5, top_k=all: candidate_genes=144, shared=38, Jaccard=0.106742, legacy_recall=0.152, precision=0.264
- score=adj_p_val <= 0.25, abs_logfc_min=0.5, top_k=250: candidate_genes=250, shared=44, Jaccard=0.096491, legacy_recall=0.176, precision=0.176
- score=adj_p_val <= 0.5, abs_logfc_min=0.5, top_k=250: candidate_genes=250, shared=44, Jaccard=0.096491, legacy_recall=0.176, precision=0.176
- score=adj_p_val <= 1, abs_logfc_min=0.5, top_k=250: candidate_genes=250, shared=44, Jaccard=0.096491, legacy_recall=0.176, precision=0.176
- score=adj_p_val <= 0.1, abs_logfc_min=0.5, top_k=100: candidate_genes=100, shared=30, Jaccard=0.093750, legacy_recall=0.120, precision=0.300
- score=adj_p_val <= 0.25, abs_logfc_min=0.5, top_k=100: candidate_genes=100, shared=30, Jaccard=0.093750, legacy_recall=0.120, precision=0.300

## Interpretation

This is not a set-name or comparison-coverage issue: the same set name and comparison exist in both outputs.
After the identifier-preservation patch, this is no longer explained by numeric row IDs in the reproduced GMT.
The difference is caused by the reproduced DE ranking and significance results. The reproduced GMT is built from genes that are adjusted-significant in the positive direction and ranked within the top 250 for that comparison.
The legacy GMT must therefore reflect different upstream DE statistics, filtering, mapping, or final membership logic for this comparison, because most of its 250 genes do not survive the reproduced inclusion rule.

## Output Files

- `selected_low_overlap_set_summary.v1.tsv`
- `legacy_gene_status_in_reproduction.v1.tsv`
- `reproduced_gene_status.v1.tsv`
- `legacy_exclusion_reason_summary.v1.tsv`
- `threshold_sweep_legacy_recovery.v1.tsv`
- `legacy_recovery_threshold_summary.v1.tsv`
- `top_legacy_genes_by_reproduction_adj_p_val.v1.tsv`
- `top_reproduced_only_genes.v1.tsv`
- `processed_matrix_identifier_summary.v1.tsv`
