# GTEx Step 1 Model Catalog

## Scope

This file fulfills step 1 of [GTEx_model_plan.txt](/home/ryank/software/geneset_extractors/GTEx_model_plan.txt:1) from scratch, using only:

- the current `dig-gene-set-extractors` code and docs in this workspace
- the current GTEx bulk-expression release target named in the plan

This catalog intentionally ignores everything under `geneset-extractor-dev/GTEx/archive/`.

## Current Inputs And Constraints

- The plan points to `https://gtexportal.org/home/downloads/adult-gtex/bulk_tissue_expression`.
- That GTEx downloads page is JavaScript-heavy, so the latest release was verified indirectly from the current Adult GTEx CFDE index on April 23, 2026.
- The current indexed bulk RNA-seq counts release is `GTEx_Analysis_v10_RNASeQCv2.4.2_gene_reads.gct.gz`.
- The current indexed per-tissue collection is `gs://adult-gtex/bulk-gex/v10/rna-seq/counts-by-tissue/`.
- The current DIG workflow boundary is:
  - `workflows rna_de_prepare` for bulk RNA-seq DE fitting
  - `convert rna_deg_multi` for turning `deg_long.tsv` into per-comparison gene sets and GMT output

## Model Design Rules

Each proposed model is supported by the current codebase and varies only knobs that the current implementation actually exposes.

The highest-value knobs for GTEx gene inclusion in the final GMT are:

1. DE fit mode: `modern` vs `harmonizome`
2. DE backend: `auto`, `lightweight`, `r_limma_voom`
3. Sample balancing: all eligible samples vs deterministic equal-sized pools
4. Expression-filter scope: `contrast` vs `stratum`
5. Covariate adjustment: none vs `SEX`
6. Extractor post-processing mode: `harmonizome` preset vs explicit legacy-mode settings
7. Ranking mode: signed FDR, signed raw-p, model statistic, hybrid score, effect size
8. Explicit row filters: `padj_max`, `min_abs_logfc`
9. GMT export source and size plan: `selected` vs `full`, top-150/250/300
10. Technical-gene exclusion and biotype restriction rules

## Models

### M1 `modern_auto_harmonizome_default`

- Proposal: `B`
- Intent: current repo-default style baseline for GTEx-like bulk data
- Workflow:
  - `de_mode=modern`
  - `backend=auto`
  - `balance_groups=false`
  - `gene_filter_scope=contrast`
  - `covariates=SEX`
- Extractor:
  - `postprocess_mode=harmonizome`
  - resolved extractor behavior: signed FDR ranking, `padj<=0.05`, threshold selection, GMT from selected rows, top-250 signed sets, no default technical excludes, no protein-coding restriction
- Expected effect on gene inclusion:
  - includes all eligible samples
  - keeps the newer harmonizome-style signature construction logic

### M2 `harmonizome_auto_harmonizome_default`

- Proposal: `B`
- Intent: conservative GTEx bulk baseline using the workflow preset and current extractor preset together
- Workflow:
  - `de_mode=harmonizome`
  - `backend=auto`
  - `balance_groups=true`
  - `balance_seed=1`
  - `gene_filter_scope=stratum`
  - `covariates=SEX`
- Extractor:
  - `postprocess_mode=harmonizome`
- Expected effect on gene inclusion:
  - removes sample-size imbalance as a source of broad generic signatures
  - retains harmonizome-style significance-driven set construction

### M3 `harmonizome_limma_harmonizome_default`

- Proposal: `B`
- Intent: same as M2, but forces the audit-friendly limma/voom backend when available
- Workflow:
  - `de_mode=harmonizome`
  - `backend=r_limma_voom`
  - `balance_groups=true`
  - `balance_seed=1`
  - `gene_filter_scope=stratum`
  - `covariates=SEX`
- Extractor:
  - `postprocess_mode=harmonizome`
- Expected effect on gene inclusion:
  - isolates backend choice from extractor choice
  - useful to compare against `lightweight` and `auto`

### M4 `harmonizome_lightweight_explicit_harm_base`

- Proposal: `A`
- Intent: explicit parameter-sweep base that recreates harmonizome-style extraction without relying on the preset override
- Workflow:
  - `de_mode=harmonizome`
  - `backend=lightweight`
  - `balance_groups=true`
  - `balance_seed=1`
  - `gene_filter_scope=stratum`
  - `covariates=SEX`
- Extractor:
  - `postprocess_mode=legacy`
  - `score_mode=signed_neglog10padj`
  - `padj_max=0.05`
  - `select=threshold`
  - `min_score=1.30103`
  - `gmt_source=selected`
  - `gmt_topk_list=250`
  - `gmt_min_genes=5`
  - `gmt_max_genes=250`
  - `disable_default_excludes=true`
  - `gmt_biotype_allowlist=''`
  - `emit_small_gene_sets=true`
- Expected effect on gene inclusion:
  - acts as the stable sweep base for score, threshold, and GMT-size perturbations

### M5 `harmonizome_lightweight_signed_rawp`

- Proposal: `A`
- Intent: test whether raw p-value ordering changes membership after the same FDR gate
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `score_mode=signed_neglog10pvalue`
- Expected effect on gene inclusion:
  - should mostly perturb tied or borderline genes
  - useful when raw-p ordering is preferred inside an explicit FDR-filtered subset

### M6 `harmonizome_lightweight_stat_top250`

- Proposal: `A`
- Intent: test model-statistic ranking instead of significance-threshold ranking
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `score_mode=stat`
  - `select=top_k`
  - `top_k=250`
  - `min_score=NA`
- Expected effect on gene inclusion:
  - favors model-statistic magnitude instead of threshold-defined significance

### M7 `harmonizome_lightweight_hybrid_top250`

- Proposal: `A`
- Intent: test hybrid effect-size plus significance ranking
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `score_mode=logfc_times_neglog10p`
  - `select=top_k`
  - `top_k=250`
  - `min_score=NA`
- Expected effect on gene inclusion:
  - tends to elevate larger effects while still rewarding stable p-values

### M8 `harmonizome_lightweight_logfc_fdr005_lfc025`

- Proposal: `A`
- Intent: effect-size-first alternative after conservative filtering
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `score_mode=logfc`
  - `padj_max=0.05`
  - `min_abs_logfc=0.25`
  - `select=top_k`
  - `top_k=250`
  - `min_score=NA`
- Expected effect on gene inclusion:
  - prioritizes larger fold-change genes among already significant rows

### M9 `harmonizome_lightweight_selected150`

- Proposal: `A`
- Intent: compact harmonizome-like output
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `gmt_topk_list=150`
  - `gmt_max_genes=150`
- Expected effect on gene inclusion:
  - forces a more compact gene library
  - drops lower-ranked tail genes relative to M4

### M10 `harmonizome_lightweight_selected300`

- Proposal: `A`
- Intent: expanded harmonizome-like output
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `gmt_topk_list=300`
  - `gmt_max_genes=300`
- Expected effect on gene inclusion:
  - admits lower-ranked tail genes
  - tests whether biology improves or degrades with larger sets

### M11 `harmonizome_lightweight_fdr001`

- Proposal: `A`
- Intent: stricter FDR gate
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `padj_max=0.01`
  - `min_score=2.0`
- Expected effect on gene inclusion:
  - strongly trims borderline genes
  - useful for conservative high-confidence sets

### M12 `harmonizome_lightweight_fdr005_lfc050`

- Proposal: `A`
- Intent: significance plus stronger effect-size filter
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `min_abs_logfc=0.5`
- Expected effect on gene inclusion:
  - removes low-effect but highly powered genes
  - emphasizes larger age-shift programs

### M13 `harmonizome_lightweight_fullrank250`

- Proposal: `A`
- Intent: test whether GMT should come from the full ranked table rather than only selected rows
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `gmt_source=full`
- Expected effect on gene inclusion:
  - allows non-selected but highly ranked rows to re-enter GMT export
  - isolates `gmt_source` as a direct gene-membership knob

### M14 `modern_lightweight_explicit_harm_sex`

- Proposal: `B`
- Intent: use all eligible samples but keep the same harmonizome-like extraction policy
- Workflow:
  - `de_mode=modern`
  - `backend=lightweight`
  - `balance_groups=false`
  - `gene_filter_scope=contrast`
  - `covariates=SEX`
- Extractor:
  - same explicit settings as M4
- Expected effect on gene inclusion:
  - isolates the effect of balancing and stratum-wide gene filtering

### M15 `modern_lightweight_explicit_harm_nocov`

- Proposal: `B`
- Intent: maximum-sample modern fit without explicit covariates
- Workflow:
  - same as M14 except `covariates=none`
- Extractor:
  - same explicit settings as M4
- Expected effect on gene inclusion:
  - useful stress-test for generic or technical signatures

### M16 `modern_lightweight_stratumfilter_sex`

- Proposal: `B`
- Intent: isolate gene-filter scope from sample balancing
- Workflow:
  - `de_mode=modern`
  - `backend=lightweight`
  - `balance_groups=false`
  - `gene_filter_scope=stratum`
  - `covariates=SEX`
- Extractor:
  - same explicit settings as M4
- Expected effect on gene inclusion:
  - tests whether stratum-wide expression filtering alone materially changes set membership

### M17 `harmonizome_lightweight_explicit_harm_nocov`

- Proposal: `B`
- Intent: harmonizome preset without explicit covariates
- Workflow:
  - same as M4 except `covariates=none`
- Extractor:
  - same as M4
- Expected effect on gene inclusion:
  - specifically tests the value of sex adjustment in balanced broad-tissue contrasts

### M18 `harmonizome_lightweight_technical_excludes`

- Proposal: `B`
- Intent: harmonizome-style DE but with legacy-style technical gene filtering restored
- Workflow:
  - same as M4
- Extractor changes from M4:
  - `disable_default_excludes=false`
- Expected effect on gene inclusion:
  - directly tests whether mitochondrial/ribosomal/global-family removal improves specificity

### M19 `harmonizome_lightweight_protein_coding_gtf`

- Proposal: `B`
- Intent: harmonizome-style DE with explicit protein-coding-only GMT emission
- Workflow:
  - same as M4
- Annotation:
  - requires `--gtf` during extraction
- Extractor changes from M4:
  - `gmt_biotype_allowlist=protein_coding`
- Expected effect on gene inclusion:
  - removes non-protein-coding genes from GMT output
  - only meaningful when gene biotypes are supplied via GTF annotation

### M20 `harmonizome_lightweight_gtf_symbol_fallback`

- Proposal: `B`
- Intent: defensible fallback if v10 symbols are incomplete after preprocessing
- Workflow:
  - same as M4
- Annotation:
  - use `--gtf` if symbols are missing or sparse
- Extractor changes from M4:
  - `gmt_require_symbol=false`
- Expected effect on gene inclusion:
  - preserves genes that would otherwise be dropped because of missing symbols

### M21 `harmonizome_limma_explicit_harm_sex`

- Proposal: `B`
- Intent: limma/voom version of the explicit harmonizome-like extractor base
- Workflow:
  - `de_mode=harmonizome`
  - `backend=r_limma_voom`
  - `balance_groups=true`
  - `balance_seed=1`
  - `gene_filter_scope=stratum`
  - `covariates=SEX`
- Extractor:
  - same explicit settings as M4
- Expected effect on gene inclusion:
  - cleanly isolates DE backend while avoiding extractor-preset overrides

### M22 `modern_limma_explicit_harm_sex`

- Proposal: `B`
- Intent: full-sample limma/voom alternative with harmonizome-like extraction
- Workflow:
  - `de_mode=modern`
  - `backend=r_limma_voom`
  - `balance_groups=false`
  - `gene_filter_scope=contrast`
  - `covariates=SEX`
- Extractor:
  - same explicit settings as M4
- Expected effect on gene inclusion:
  - compares backend and sample-balancing choices simultaneously against M21 and M14

## Exclusions From This Catalog

The following are intentionally not modeled in step 1:

- `r_dream`: current code supports it for repeated-measures designs, but GTEx per-tissue age-bin comparisons are not naturally repeated-measures within a single tissue run, and `de_mode=harmonizome` explicitly rejects it.
- batch-column sweeps: the current harmonizome preset disallows batch columns, and step 1 should stay within verified, auditable GTEx bulk workflows.
- duplicate-gene aggregation sweeps: GTEx gene-level count tables are expected to be unique at the feature-id level, so this is lower priority than DE/ranking/export knobs.

## Recommended Order

1. Run anchors first: `M1`, `M2`, `M3`, `M4`.
2. Run score and threshold sweeps next: `M5` to `M13`.
3. Run workflow-design alternatives: `M14` to `M17`.
4. Run annotation and technical-filter alternatives: `M18` to `M20`.
5. Run backend validation last: `M21`, `M22`.

## Output Files From Step 1

- `model_catalog.md`: this detailed model file
- `model_manifest.tsv.gz`: one row per model with explicit settings
- `model_family_summary.tsv.gz`: counts and rationale by family
- `output_manifest.tsv.gz`: manifest of step-1 deliverables
- `run_summary.md`: compact summary of the step-1 result
- `commands.md`: actual commands used to derive this proposal
- `step1_execution.log`: execution log for this proposal-writing step
