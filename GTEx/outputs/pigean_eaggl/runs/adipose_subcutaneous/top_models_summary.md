# Top GTEx Models Summary

- tissue: `adipose_subcutaneous`
- model_groups: `models,tissue_models`
- top_n_per_group: `5`
- ranking rule: `total_score` descending, then `num_strong_queries`, then `mean_score`, then `best_query_score`
- biology score source: existing PIGEAN/EAGGL biology summaries from `summarize_pigean_eaggl_results.py`
- identical-model groups source: existing `identical_model_groups.tsv` outputs

## models

Top models are ranked by `total_score`, then `num_strong_queries`, then `mean_score`, then `best_query_score`.

Metric definitions:
- `score` is first computed per query by the existing PIGEAN/EAGGL biology summarizer.
- Per query, the script scans top PIGEAN labels, top EAGGL cluster labels, and top EAGGL factor labels for tissue-expected biology keywords.
- PIGEAN matches contribute base weight `3.0`, EAGGL cluster matches contribute base weight `2.0`, and EAGGL factor matches contribute base weight `1.5`.
- Within each source, earlier ranked labels count more: label rank `r` contributes `base_weight / r` when it matches expected biology.
- `total_score` is the sum of those per-query scores across all queries for the model.
- `num_strong_queries` counts how many model queries had per-query `score >= 6`.
- `mean_score` is `total_score / num_queries` for that model.
- `best_query_score` is the maximum per-query score among that model's queries.
- `best_query_reason` records which biology categories were matched in PIGEAN, EAGGL clusters, and EAGGL factors for that best query.
- The ranking therefore rewards models that repeatedly produce high-scoring, tissue-relevant query labels, not just one isolated hit.

### Rank 1: `M1`

- Score summary: total `52.14`, mean `5.214`, strong queries `3` of `10`
- Why it ranked here: ranked by total_score=52.14, num_strong_queries=3, mean_score=5.214; best query M1__age50_20__neg scored 13.3512 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG3`
- Group members: `M1,M22`
- Representative model: `M1`
- Representative reason: forced backend=None
- Representative definition: current repo-default style baseline for GTEx-like bulk data | workflow: `de_mode=modern`; `backend=auto`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: `postprocess_mode=harmonizome`; resolved extractor behavior: signed FDR ranking, `padj<=0.05`, threshold selection, GMT from selected rows, top-250 signed sets, no default technical excludes, no protein-coding restriction
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `SYNCRIP_TARGET_GENES | KEGG_AMINO_SUGAR_AND_NUCLEOTIDE_SUGAR_METABOLISM | WEST_ADRENOCORTICAL_CARCINOMA_VS_ADENOMA_UP | GOBP_REGULATION_OF_MEMBRANE_DEPOLARIZATION | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | MOOTHA_HUMAN_MITODB_6_2002 | HALLMARK_OXIDATIVE_PHOSPHORYLATION | HALLMARK_ADIPOGENESIS | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D`

### Rank 2: `M22`

- Score summary: total `51.4414`, mean `5.1441`, strong queries `4` of `10`
- Why it ranked here: ranked by total_score=51.4414, num_strong_queries=4, mean_score=5.1441; best query M22__age40_20__neg scored 12.4653 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG3`
- Group members: `M1,M22`
- Representative model: `M1`
- Representative reason: forced backend=None
- Representative definition: current repo-default style baseline for GTEx-like bulk data | workflow: `de_mode=modern`; `backend=auto`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: `postprocess_mode=harmonizome`; resolved extractor behavior: signed FDR ranking, `padj<=0.05`, threshold selection, GMT from selected rows, top-250 signed sets, no default technical excludes, no protein-coding restriction
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `GOCC_EMC_COMPLEX | CREIGHTON_AKT1_SIGNALING_VIA_MTOR_UP | SYNCRIP_TARGET_GENES | mp_abnormal_brown_adipose_tissue_morphology | GOMF_MHC_CLASS_I_PROTEIN_BINDING`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | MOOTHA_HUMAN_MITODB_6_2002 | HALLMARK_OXIDATIVE_PHOSPHORYLATION | GOCC_MITOCHONDRIAL_MATRIX | GOCC_MITOCHONDRIAL_ENVELOPE`

### Rank 3: `M14`

- Score summary: total `49.6139`, mean `4.9614`, strong queries `5` of `10`
- Why it ranked here: ranked by total_score=49.6139, num_strong_queries=5, mean_score=4.9614; best query M14__age60_20__neg scored 10.3475 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: `MG4`
- Group members: `M14,M16`
- Representative model: `M14`
- Representative reason: forced backend=None
- Representative definition: use all eligible samples but keep the same harmonizome-like extraction policy | workflow: `de_mode=modern`; `backend=lightweight`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: same explicit settings as M4
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | GOBP_REGULATION_OF_MEMBRANE_DEPOLARIZATION | BURTON_ADIPOGENESIS_5 | SOGA_COLORECTAL_CANCER_MYC_DN | MORF_ATOX1`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | MOOTHA_HUMAN_MITODB_6_2002 | HALLMARK_ADIPOGENESIS`

### Rank 4: `M16`

- Score summary: total `48.8567`, mean `4.8857`, strong queries `5` of `10`
- Why it ranked here: ranked by total_score=48.8567, num_strong_queries=5, mean_score=4.8857; best query M16__age50_20__neg scored 9.0682 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG4`
- Group members: `M14,M16`
- Representative model: `M14`
- Representative reason: forced backend=None
- Representative definition: use all eligible samples but keep the same harmonizome-like extraction policy | workflow: `de_mode=modern`; `backend=lightweight`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: same explicit settings as M4
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `WEST_ADRENOCORTICAL_CARCINOMA_VS_ADENOMA_UP | BURTON_ADIPOGENESIS_5 | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA1_DN | MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA2_DN`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | HALLMARK_ADIPOGENESIS | MOOTHA_HUMAN_MITODB_6_2002`

### Rank 5: `M15`

- Score summary: total `46.4863`, mean `4.6486`, strong queries `3` of `10`
- Why it ranked here: ranked by total_score=46.4863, num_strong_queries=3, mean_score=4.6486; best query M15__age50_20__neg scored 12.4958 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: unique model
- Group members: `M15`
- Representative model: `M15`
- Representative reason: unique model; no identical-model cluster
- Representative definition: maximum-sample modern fit without explicit covariates | workflow: same as M14 except `covariates=none` | extractor: same explicit settings as M4
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `BURTON_ADIPOGENESIS_5 | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA2_DN | KEGG_AMINO_SUGAR_AND_NUCLEOTIDE_SUGAR_METABOLISM | MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR6765_3P`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | HALLMARK_ADIPOGENESIS | MOOTHA_HUMAN_MITODB_6_2002`

### Represented Model Groups

- `MG3` represented by top model `M1`; representative model `M1`; members `M1,M22`
- `MG4` represented by top model `M14`; representative model `M14`; members `M14,M16`
- unique model `M15` is its own represented group

## tissue_models

Top models are ranked by `total_score`, then `num_strong_queries`, then `mean_score`, then `best_query_score`.

Metric definitions:
- `score` is first computed per query by the existing PIGEAN/EAGGL biology summarizer.
- Per query, the script scans top PIGEAN labels, top EAGGL cluster labels, and top EAGGL factor labels for tissue-expected biology keywords.
- PIGEAN matches contribute base weight `3.0`, EAGGL cluster matches contribute base weight `2.0`, and EAGGL factor matches contribute base weight `1.5`.
- Within each source, earlier ranked labels count more: label rank `r` contributes `base_weight / r` when it matches expected biology.
- `total_score` is the sum of those per-query scores across all queries for the model.
- `num_strong_queries` counts how many model queries had per-query `score >= 6`.
- `mean_score` is `total_score / num_queries` for that model.
- `best_query_score` is the maximum per-query score among that model's queries.
- `best_query_reason` records which biology categories were matched in PIGEAN, EAGGL clusters, and EAGGL factors for that best query.
- The ranking therefore rewards models that repeatedly produce high-scoring, tissue-relevant query labels, not just one isolated hit.

### Rank 1: `T6`

- Score summary: total `11.5555`, mean `5.7778`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=11.5555, num_strong_queries=1, mean_score=5.7778; best query T6__adipose_subcutaneous__neg scored 9.9055 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG2`
- Group members: `T6,T7`
- Representative model: `T6`
- Representative reason: strictness model; auto backend; standard gct_symbols_only annotation; extractor=legacy/signed_neglog10padj
- Representative definition: stricter threshold model emphasizing higher-confidence age associations | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=legacy; extractor_score_mode=signed_neglog10padj; extractor_select=threshold; extractor_padj_max=0.01; extractor_min_score=2.0; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests robustness to more stringent significance filtering
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 2: `T4`

- Score summary: total `11.3944`, mean `5.6972`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=11.3944, num_strong_queries=1, mean_score=5.6972; best query T4__adipose_subcutaneous__neg scored 9.7444 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG1`
- Group members: `T1,T3,T4,T5`
- Representative model: `T1`
- Representative reason: core model; auto backend; standard gct_symbols_only annotation; canonical harmonizome-style extractor defaults
- Representative definition: canonical ranked continuous-age model with SEX adjustment | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=harmonizome; extractor_score_mode=auto; extractor_select=top_k; extractor_gmt_biotype_allowlist=protein_coding | rationale: recommended default tissue aging model
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 3: `T3`

- Score summary: total `10.8899`, mean `5.445`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.8899, num_strong_queries=1, mean_score=5.445; best query T3__adipose_subcutaneous__neg scored 9.2399 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: `MG1`
- Group members: `T1,T3,T4,T5`
- Representative model: `T1`
- Representative reason: core model; auto backend; standard gct_symbols_only annotation; canonical harmonizome-style extractor defaults
- Representative definition: canonical ranked continuous-age model with SEX adjustment | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=harmonizome; extractor_score_mode=auto; extractor_select=top_k; extractor_gmt_biotype_allowlist=protein_coding | rationale: recommended default tissue aging model
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 4: `T7`

- Score summary: total `10.7745`, mean `5.3872`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.7745, num_strong_queries=1, mean_score=5.3872; best query T7__adipose_subcutaneous__neg scored 9.1245 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: `MG2`
- Group members: `T6,T7`
- Representative model: `T6`
- Representative reason: strictness model; auto backend; standard gct_symbols_only annotation; extractor=legacy/signed_neglog10padj
- Representative definition: stricter threshold model emphasizing higher-confidence age associations | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=legacy; extractor_score_mode=signed_neglog10padj; extractor_select=threshold; extractor_padj_max=0.01; extractor_min_score=2.0; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests robustness to more stringent significance filtering
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 5: `T2`

- Score summary: total `10.7455`, mean `5.3727`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.7455, num_strong_queries=1, mean_score=5.3727; best query T2__adipose_subcutaneous__neg scored 9.3955 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: unique model
- Group members: `T2`
- Representative model: `T2`
- Representative reason: unique model; no identical-model cluster
- Representative definition: same as T1 but without SEX adjustment | settings: workflow_covariates=none; annotation_mode=gct_symbols_only; extractor_postprocess_mode=harmonizome; extractor_score_mode=auto; extractor_select=top_k; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests whether SEX materially changes the tissue aging signature
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_ganglion_cell_morphology | mp_abnormal_retina_inner_limiting_membrane_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Represented Model Groups

- `MG2` represented by top model `T6`; representative model `T6`; members `T6,T7`
- `MG1` represented by top model `T4`; representative model `T1`; members `T1,T3,T4,T5`
- unique model `T2` is its own represented group
