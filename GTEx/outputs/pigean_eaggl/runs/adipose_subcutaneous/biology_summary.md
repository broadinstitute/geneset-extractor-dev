# Adipose Subcutaneous PIGEAN EAGGL Summary

This summary scores each model by how often its PIGEAN enrichments and EAGGL labels recover adipose-subcutaneous-relevant biology.

Directional expectations used:
- positive age contrasts: immune/inflammation and ECM/fibrosis
- negative age contrasts: adipocyte/lipid and mitochondrial/energetic programs

- queries summarized: 220
- top labels inspected per stage: 20

Top models:
- `M1`: total_score=52.14, strong_queries=3, top_categories=mitochondria_energetics,ecm_fibrosis,adipocyte_lipid,immune_inflammation
- `M22`: total_score=51.4414, strong_queries=4, top_categories=mitochondria_energetics,ecm_fibrosis,adipocyte_lipid,immune_inflammation
- `M14`: total_score=49.6139, strong_queries=5, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation
- `M16`: total_score=48.8567, strong_queries=5, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation
- `M15`: total_score=46.4863, strong_queries=3, top_categories=mitochondria_energetics,adipocyte_lipid,ecm_fibrosis,immune_inflammation

Files:
- `biology_model_summary.tsv.gz`
- `biology_query_summary.tsv.gz`
