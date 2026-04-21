# PIGEAN EAGGL Test v3

- selected_set_name: `GTEx_AdiposeTissue_20-29_vs_30-39_Up`
- n_sources: 3
- n_shared_across_all_three: 3

## Gene-set overlap

- GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021: n_genes=250
- gtex_harmonizome_analysis_v1: n_genes=250
- gtex_no_harmonizome_analysis_v1: n_genes=200

- gtex_harmonizome_analysis_v1 vs GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021: intersection=4, union=496, jaccard=0.008, overlap_coefficient=0.016
- gtex_harmonizome_analysis_v1 vs gtex_no_harmonizome_analysis_v1: intersection=184, union=266, jaccard=0.692, overlap_coefficient=0.920
- gtex_no_harmonizome_analysis_v1 vs GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021: intersection=4, union=446, jaccard=0.009, overlap_coefficient=0.020

## EAGGL Take-home Messages

- GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021: top factor `YAO_TEMPORAL_RESPONSE_TO_PROGESTERONE_CLUSTER_3` (any_relevance=0.466, lambda=0.0589); top programs were YAO_TEMPORAL_RESPONSE_TO_PROGESTERONE_CLUSTER_3, GOBP_REGULATION_OF_MEMBRANE_INVAGINATION, DESCARTES_FETAL_LUNG_NEUROENDOCRINE_CELLS, FULLER_PBMC_F_TULARENSIS_VACCINE_LVS_AGE_22_54YO_336HR_DN, GOBP_NEGATIVE_REGULATION_OF_T_CELL_CYTOKINE_PRODUCTION; recurring top genes included JCHAIN, JSRP1, NUGGC, TRAT1, MYO1A, STAP1, LGI1, MMP27, GBP7, PRKG2.
- gtex_harmonizome_analysis_v1: top factor `REACTOME_PD_1_SIGNALING` (any_relevance=0.459, lambda=0.0829); top programs were REACTOME_PD_1_SIGNALING, GOBP_MYD88_DEPENDENT_TOLL_LIKE_RECEPTOR_SIGNALING_PATHWAY, GSE23502_WT_VS_HDC_KO_MYELOID_DERIVED_SUPPRESSOR_CELL_BM_UP, GSE6674_ANTI_IGM_VS_CPG_STIM_BCELL_UP, MODULE_543; recurring top genes included HLA-DQA1, HLA-DRA, CIITA, HLA-DMB, HLA-DPA1, TRAF6, IKBKB, IRAK4, ABRAXAS1, VPS13C.
- gtex_no_harmonizome_analysis_v1: top factor `GSE42088_UNINF_VS_LEISHMANIA_INF_DC_24H_UP` (any_relevance=0.445, lambda=0.0462); top programs were GSE42088_UNINF_VS_LEISHMANIA_INF_DC_24H_UP, MODULE_293, NUNODA_RESPONSE_TO_DASATINIB_IMATINIB_DN, GSE6674_ANTI_IGM_VS_CPG_STIM_BCELL_UP, GSE22886_UNSTIM_VS_IL15_STIM_NKCELL_UP; recurring top genes included HSD17B11, SCPEP1, PIGB, SIGIRR, GALC, HLA-DOA, HLA-DMB, HLA-DRA, SLC25A30, GAS6.

## Cross-run comparison

- GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021 vs gtex_harmonizome_analysis_v1: top5_label_overlap_n=0, top5_label_jaccard=0.000, top_gene_overlap_n=0, top_gene_jaccard=0.000
- GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021 vs gtex_no_harmonizome_analysis_v1: top5_label_overlap_n=0, top5_label_jaccard=0.000, top_gene_overlap_n=0, top_gene_jaccard=0.000
- gtex_harmonizome_analysis_v1 vs gtex_no_harmonizome_analysis_v1: top5_label_overlap_n=1, top5_label_jaccard=0.111, top_gene_overlap_n=2, top_gene_jaccard=0.111

## Run outputs

- GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021: pigean_bundle=`pigean_to_eaggl.v1.tar.gz`, eaggl_factors=`eaggl.factors.v1.tsv`, n_input_genes=250
- gtex_harmonizome_analysis_v1: pigean_bundle=`pigean_to_eaggl.v1.tar.gz`, eaggl_factors=`eaggl.factors.v1.tsv`, n_input_genes=250
- gtex_no_harmonizome_analysis_v1: pigean_bundle=`pigean_to_eaggl.v1.tar.gz`, eaggl_factors=`eaggl.factors.v1.tsv`, n_input_genes=200
