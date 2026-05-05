# Top GTEx Models Summary

- tissue: `adipose_subcutaneous`
- model_groups: `age_binned,continuous_age`
- top_n_per_group: `5`
- ranking rule: `total_score` descending, then `num_strong_queries`, then `mean_score`, then `best_query_score`
- biology score source: existing PIGEAN/EAGGL biology summaries from `summarize_pigean_eaggl_results.py`
- identical-model groups source: existing `identical_model_groups.tsv` outputs

## age_binned

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

### Rank 1: `AB1`

- Score summary: total `54.2506`, mean `5.4251`, strong queries `4` of `10`
- Why it ranked here: ranked by total_score=54.2506, num_strong_queries=4, mean_score=5.4251; best query AB1__age40_20__neg scored 12.4708 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG3`
- Group members: `AB1,AB22`
- Representative model: `AB1`
- Representative reason: anchor model; auto backend; standard gct_symbols_only annotation; canonical harmonizome-style extractor defaults; no balancing
- Representative definition: current repo-default style baseline for GTEx-like bulk data | workflow: `de_mode=modern`; `backend=auto`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: `postprocess_mode=harmonizome`; resolved extractor behavior: signed FDR ranking, `padj<=0.05`, threshold selection, GMT from selected rows, top-250 signed sets, no default technical excludes, no protein-coding restriction
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `GOCC_EMC_COMPLEX | CREIGHTON_AKT1_SIGNALING_VIA_MTOR_UP | SYNCRIP_TARGET_GENES | mp_abnormal_brown_adipose_tissue_morphology | GOMF_MHC_CLASS_I_PROTEIN_BINDING`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | MOOTHA_HUMAN_MITODB_6_2002 | HALLMARK_OXIDATIVE_PHOSPHORYLATION | GOCC_MITOCHONDRIAL_MATRIX | GOCC_MITOCHONDRIAL_ENVELOPE`

### Rank 2: `AB14`

- Score summary: total `48.3896`, mean `4.839`, strong queries `4` of `10`
- Why it ranked here: ranked by total_score=48.3896, num_strong_queries=4, mean_score=4.839; best query AB14__age50_20__neg scored 10.4572 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG4`
- Group members: `AB14,AB16`
- Representative model: `AB14`
- Representative reason: defensible alternative; forced backend=lightweight; standard gct_symbols_only annotation; extractor=legacy/signed_neglog10padj; no balancing
- Representative definition: use all eligible samples but keep the same harmonizome-like extraction policy | workflow: `de_mode=modern`; `backend=lightweight`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: same explicit settings as AB4
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `WEST_ADRENOCORTICAL_CARCINOMA_VS_ADENOMA_UP | BURTON_ADIPOGENESIS_5 | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA1_DN | MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA2_DN`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | HALLMARK_ADIPOGENESIS | MOOTHA_HUMAN_MITODB_6_2002`

### Rank 3: `AB15`

- Score summary: total `48.1062`, mean `4.8106`, strong queries `3` of `10`
- Why it ranked here: ranked by total_score=48.1062, num_strong_queries=3, mean_score=4.8106; best query AB15__age50_20__neg scored 13.3924 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: unique model
- Group members: `AB15`
- Representative model: `AB15`
- Representative reason: unique model; no identical-model cluster
- Representative definition: maximum-sample modern fit without explicit covariates | workflow: same as AB14 except `covariates=none` | extractor: same explicit settings as AB4
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `BURTON_ADIPOGENESIS_5 | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA2_DN | KEGG_AMINO_SUGAR_AND_NUCLEOTIDE_SUGAR_METABOLISM | MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR6765_3P`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | HALLMARK_ADIPOGENESIS | MOOTHA_HUMAN_MITODB_6_2002`

### Rank 4: `AB21`

- Score summary: total `46.9398`, mean `4.694`, strong queries `3` of `10`
- Why it ranked here: ranked by total_score=46.9398, num_strong_queries=3, mean_score=4.694; best query AB21__age40_20__neg scored 11.9556 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG2`
- Group members: `AB2,AB3,AB21`
- Representative model: `AB2`
- Representative reason: anchor model; auto backend; standard gct_symbols_only annotation; canonical harmonizome-style extractor defaults; balanced groups
- Representative definition: conservative GTEx bulk baseline using the workflow preset and current extractor preset together | workflow: `de_mode=harmonizome`; `backend=auto`; `balance_groups=true`; `balance_seed=1`; `gene_filter_scope=stratum`; `covariates=SEX` | extractor: `postprocess_mode=harmonizome`
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `SYNCRIP_TARGET_GENES | BURTON_ADIPOGENESIS_5 | mp_abnormal_coronal_suture_morphology | GSE22886_NEUTROPHIL_VS_DC_DN | BURTON_ADIPOGENESIS_6`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | HALLMARK_OXIDATIVE_PHOSPHORYLATION | HALLMARK_ADIPOGENESIS | MOOTHA_HUMAN_MITODB_6_2002 | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS`

### Rank 5: `AB16`

- Score summary: total `46.8021`, mean `4.6802`, strong queries `4` of `10`
- Why it ranked here: ranked by total_score=46.8021, num_strong_queries=4, mean_score=4.6802; best query AB16__age50_20__neg scored 10.4572 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: `MG4`
- Group members: `AB14,AB16`
- Representative model: `AB14`
- Representative reason: defensible alternative; forced backend=lightweight; standard gct_symbols_only annotation; extractor=legacy/signed_neglog10padj; no balancing
- Representative definition: use all eligible samples but keep the same harmonizome-like extraction policy | workflow: `de_mode=modern`; `backend=lightweight`; `balance_groups=false`; `gene_filter_scope=contrast`; `covariates=SEX` | extractor: same explicit settings as AB4
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `WEST_ADRENOCORTICAL_CARCINOMA_VS_ADENOMA_UP | BURTON_ADIPOGENESIS_5 | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA1_DN | MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA2_DN`
- Best query top EAGGL labels: `GOCC_MITOCHONDRION | WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | HALLMARK_ADIPOGENESIS | MOOTHA_HUMAN_MITODB_6_2002`

### Represented Model Groups

- `MG3` represented by top model `AB1`; representative model `AB1`; members `AB1,AB22`
- `MG4` represented by top model `AB14`; representative model `AB14`; members `AB14,AB16`
- unique model `AB15` is its own represented group
- `MG2` represented by top model `AB21`; representative model `AB2`; members `AB2,AB3,AB21`

## continuous_age

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

### Rank 1: `AC7`

- Score summary: total `10.8048`, mean `5.4024`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.8048, num_strong_queries=1, mean_score=5.4024; best query AC7__adipose_subcutaneous__neg scored 9.1548 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: `MG2`
- Group members: `AC6,AC7`
- Representative model: `AC6`
- Representative reason: strictness model; auto backend; standard gct_symbols_only annotation; extractor=legacy/signed_neglog10padj
- Representative definition: stricter threshold model emphasizing higher-confidence age associations | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=legacy; extractor_score_mode=signed_neglog10padj; extractor_select=threshold; extractor_padj_max=0.01; extractor_min_score=2.0; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests robustness to more stringent significance filtering
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 2: `AC6`

- Score summary: total `10.8048`, mean `5.4024`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.8048, num_strong_queries=1, mean_score=5.4024; best query AC6__adipose_subcutaneous__neg scored 9.1548 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: `MG2`
- Group members: `AC6,AC7`
- Representative model: `AC6`
- Representative reason: strictness model; auto backend; standard gct_symbols_only annotation; extractor=legacy/signed_neglog10padj
- Representative definition: stricter threshold model emphasizing higher-confidence age associations | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=legacy; extractor_score_mode=signed_neglog10padj; extractor_select=threshold; extractor_padj_max=0.01; extractor_min_score=2.0; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests robustness to more stringent significance filtering
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 3: `AC2`

- Score summary: total `10.783`, mean `5.3915`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.783, num_strong_queries=1, mean_score=5.3915; best query AC2__adipose_subcutaneous__neg scored 9.433 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid,mitochondria_energetics
- Represented group: unique model
- Group members: `AC2`
- Representative model: `AC2`
- Representative reason: unique model; no identical-model cluster
- Representative definition: same as AC1 but without SEX adjustment | settings: workflow_covariates=none; annotation_mode=gct_symbols_only; extractor_postprocess_mode=harmonizome; extractor_score_mode=auto; extractor_select=top_k; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests whether SEX materially changes the tissue aging signature
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_ganglion_cell_morphology | mp_abnormal_retina_inner_limiting_membrane_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 4: `AC5`

- Score summary: total `10.6245`, mean `5.3123`, strong queries `1` of `2`
- Why it ranked here: ranked by total_score=10.6245, num_strong_queries=1, mean_score=5.3123; best query AC5__adipose_subcutaneous__neg scored 8.9745 (strong) with pigean=adipocyte_lipid,mitochondria_energetics; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: `MG1`
- Group members: `AC1,AC3,AC4,AC5`
- Representative model: `AC1`
- Representative reason: core model; auto backend; standard gct_symbols_only annotation; canonical harmonizome-style extractor defaults
- Representative definition: canonical ranked continuous-age model with SEX adjustment | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=harmonizome; extractor_score_mode=auto; extractor_select=top_k; extractor_gmt_biotype_allowlist=protein_coding | rationale: recommended default tissue aging model
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `MEBARKI_HCC_PROGENITOR_WNT_DN_BLOCKED_BY_FZD8CRD | MIR3934_5P | mp_abnormal_retina_inner_limiting_membrane_morphology | mp_abnormal_retina_ganglion_cell_morphology | BURTON_ADIPOGENESIS_5`
- Best query top EAGGL labels: `WAKABAYASHI_ADIPOGENESIS_PPARG_RXRA_BOUND_8D | GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | GOCC_MITOCHONDRION | HALLMARK_ADIPOGENESIS | GOBP_ORGANIC_ACID_METABOLIC_PROCESS`

### Rank 5: `AC10`

- Score summary: total `7.0172`, mean `3.5086`, strong queries `0` of `2`
- Why it ranked here: ranked by total_score=7.0172, num_strong_queries=0, mean_score=3.5086; best query AC10__adipose_subcutaneous__neg scored 5.1907 (partial) with pigean=adipocyte_lipid; eaggl_clusters=adipocyte_lipid,mitochondria_energetics; eaggl_factors=adipocyte_lipid
- Represented group: unique model
- Group members: `AC10`
- Representative model: `AC10`
- Representative reason: unique model; no identical-model cluster
- Representative definition: top-k model ranked by log fold-change without an explicit effect-size floor | settings: workflow_covariates=SEX; annotation_mode=gct_symbols_only; extractor_postprocess_mode=legacy; extractor_score_mode=logfc; extractor_select=top_k; extractor_padj_max=0.05; extractor_gmt_biotype_allowlist=protein_coding | rationale: tests whether simpler effect-size ranking is sufficient for tissue aging GMTs while respecting the smaller coefficient scale of continuous-age regression
- Best query matched categories: `adipocyte_lipid,mitochondria_energetics`
- Best query top PIGEAN labels: `GAO_LARGE_INTESTINE_24W_C5_LGR5POS_STEM_CELL | KEGG_MEDICUS_REFERENCE_LECTIN_PATHWAY_OF_COAGULATION_CASCADE_FIBRINOGEN_TO_FIBRIN | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA1_DN | GOBP_CELLULAR_COMPONENT_DISASSEMBLY_INVOLVED_IN_EXECUTION_PHASE_OF_APOPTOSIS | GOMF_PROTEIN_BINDING_INVOLVED_IN_HETEROTYPIC_CELL_CELL_ADHESION`
- Best query top EAGGL labels: `GOBP_SMALL_MOLECULE_METABOLIC_PROCESS | NAKAYAMA_SOFT_TISSUE_TUMORS_PCA2_DN | DESCARTES_FETAL_LIVER_HEPATOBLASTS | mp_homeostasis_metabolism_phenotype | CARRILLOREIXACH_HEPATOBLASTOMA_VS_NORMAL_DN`

### Represented Model Groups

- `MG2` represented by top model `AC7`; representative model `AC6`; members `AC6,AC7`
- unique model `AC2` is its own represented group
- `MG1` represented by top model `AC5`; representative model `AC1`; members `AC1,AC3,AC4,AC5`
- unique model `AC10` is its own represented group
