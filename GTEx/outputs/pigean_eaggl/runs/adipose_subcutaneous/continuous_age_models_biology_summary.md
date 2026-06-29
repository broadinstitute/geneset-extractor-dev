# Adipose Subcutaneous PIGEAN EAGGL Summary: continuous_age

This summary scores each continuous_age model by how often its PIGEAN enrichments and EAGGL labels recover adipose-subcutaneous-relevant biology.

Directional expectations used:
- positive age contrasts: immune/inflammation and ECM/fibrosis
- negative age contrasts: adipocyte/lipid and mitochondrial/energetic programs

- queries summarized: 20
- top labels inspected per stage: 20

Top models:
- `AC6`: total_score=10.8048, strong_queries=1, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation
- `AC7`: total_score=10.8048, strong_queries=1, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation
- `AC2`: total_score=10.783, strong_queries=1, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis
- `AC5`: total_score=10.6245, strong_queries=1, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation
- `AC10`: total_score=7.0172, strong_queries=0, top_categories=adipocyte_lipid,mitochondria_energetics,ecm_fibrosis,immune_inflammation

Files:
- `continuous_age_models_biology_model_summary.tsv.gz`
- `continuous_age_models_biology_query_summary.tsv.gz`
