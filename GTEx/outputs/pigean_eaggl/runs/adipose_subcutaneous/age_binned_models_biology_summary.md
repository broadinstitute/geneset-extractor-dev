# Adipose Subcutaneous PIGEAN EAGGL Summary: age_binned

This summary scores each age_binned model by how often its PIGEAN enrichments and EAGGL labels recover adipose-subcutaneous-relevant biology.

Directional expectations used:
- positive age contrasts: immune/inflammation and ECM/fibrosis
- negative age contrasts: adipocyte/lipid and mitochondrial/energetic programs

- queries summarized: 220
- top labels inspected per stage: 20

Top models:
- `AB1`: total_score=54.2506, strong_queries=4, top_categories=mitochondria_energetics,ecm_fibrosis,adipocyte_lipid,immune_inflammation
- `AB14`: total_score=48.3896, strong_queries=4, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation
- `AB15`: total_score=48.1062, strong_queries=3, top_categories=mitochondria_energetics,adipocyte_lipid,ecm_fibrosis,immune_inflammation
- `AB21`: total_score=46.9398, strong_queries=3, top_categories=mitochondria_energetics,ecm_fibrosis,adipocyte_lipid,immune_inflammation
- `AB16`: total_score=46.8021, strong_queries=4, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation

Files:
- `age_binned_models_biology_model_summary.tsv.gz`
- `age_binned_models_biology_query_summary.tsv.gz`
