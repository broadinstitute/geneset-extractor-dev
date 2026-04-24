# Outputs Directory Analysis Index v1

## High-Level Summary

This file describes the analysis represented by each top-level subdirectory under `outputs/`, ordered by the inferred time each output directory was first populated. The ordering is based on the earliest file modification time found within each output subdirectory. For directories that were rerun or updated later, the original first-populated time is still used for ordering, and notable later updates are mentioned in the directory description.

One directory, `outputs/eaggl_smoke_v1`, contains no files at the time this index was written, so its exact run time cannot be inferred from filesystem timestamps. It is listed near the related `outputs/eaggl_smoke_v2` smoke test.

## Chronological Output Directory Index

### 1. `outputs/gtex_harmonizome_analysis_v1`

Inferred first-populated time: 2026-04-09 22:56.

This directory contains the Harmonizome-mode GTEx aging-signature regeneration. It starts from GTEx V8 RNA-seq counts and GTEx sample/subject metadata, prepares tissue-specific matrices and age-bin comparisons, runs `geneset_extractors workflows rna_de_prepare` with Harmonizome-oriented differential-expression behavior, combines DE results, converts them into legacy-formatted GMT set names, and compares the generated GMT against `GTEx_XMT_2022-06-06_GTEx_Aging_Signatures_2021.gmt.gz`.

Main outputs include `gtex_aging_signatures_legacy_format.v1.gmt.gz`, `comparison_to_reference.v1.tsv`, `comparison_to_reference.v1.md`, `rna_de_prepare_manifest.v1.tsv`, dry-run command documentation, and the run log. The comparison report indicates 207 generated sets, 203 shared set names with the reference, 67 missing reference sets, and 4 extra generated sets.

Likely entrypoints: `src/run_gtex_harmonizome_analysis.v1.py` and `run/run_gtex_harmonizome_analysis.v1.sh`.

### 2. `outputs/gtex_no_harmonizome_analysis_v1`

Inferred first-populated time: 2026-04-09 23:34.

This directory contains the no-Harmonizome GTEx aging-signature regeneration. It uses the same GTEx V8 counts and metadata setup as the Harmonizome-mode analysis, but removes the Harmonizome-specific workflow/postprocessing behavior. The workflow uses modern DE preparation with legacy-style GMT postprocessing, then compares the generated GMT to the legacy reference.

Main outputs include `gtex_aging_signatures_legacy_format.v1.gmt.gz`, `comparison_to_reference.v1.tsv`, `comparison_to_reference.v1.md`, `rna_de_prepare_manifest.v1.tsv`, dry-run command documentation, and the run log. The comparison report indicates 266 generated sets, 262 shared set names with the reference, 8 missing reference sets, and 4 extra generated sets.

Likely entrypoints: `src/run_gtex_no_harmonizome_analysis.v1.py` and `run/run_gtex_no_harmonizome_analysis.v1.sh`.

### 3. `outputs/eaggl_gene_list_batch_v1`

Inferred first-populated time: 2026-04-10 00:06.

This directory contains an early EAGGL-only gene-list batch run or dry-run across the three GMT sources. It generated dry-run command documentation and a run summary.

Main outputs include `dry_run_commands.v1.md`, `dry_run_examples.v2.md`, `eaggl_run_summary.v1.md`, `eaggl_run_summary.v1.tsv`, `source_manifest.v1.tsv`, and the run log. The summary reports 743 total sets but no successful EAGGL outputs in this version, with many `no_enrichment`, `no_outputs`, and `error` statuses.

Likely entrypoints: `src/run_eaggl_gene_list_batch.v1.py` and `run/run_eaggl_gene_list_batch.v1.sh`.

### 4. `outputs/eaggl_smoke_v1`

Inferred first-populated time: unavailable.

This appears to be an initial EAGGL smoke-test directory. No files were found under this directory when this index was written, so it likely represents an incomplete, abandoned, or cleaned-up smoke test. Because no files are present, its exact position in the run chronology cannot be verified from filesystem timestamps.

### 5. `outputs/eaggl_smoke_v2`

Inferred first-populated time: 2026-04-10 00:08.

This directory contains a small EAGGL smoke test with a single input gene list and parameter output.

Main outputs include `input_gene_list.v1.txt` and `params_human_fix2.v1.tsv`. The parameter file shows a standalone hypergeometric gene-list EAGGL run with 250 input genes, 223 matched input genes, 27 unmatched input genes, and 1,363 retained gene sets.

### 6. `outputs/eaggl_gene_list_batch_v2`

Inferred first-populated time: 2026-04-10 00:11.

This directory contains a later EAGGL-only batch attempt over the same configured source GMTs.

Main outputs include `eaggl_run_summary.v1.md`, `eaggl_run_summary.v1.tsv`, and `source_manifest.v1.tsv`. The summary reports 743 total sets, 37 `no_enrichment`, 705 `no_outputs`, and 1 error, indicating this run also did not produce broad successful EAGGL factor outputs.

Likely entrypoints: `src/run_eaggl_gene_list_batch.v1.py` and `run/run_eaggl_gene_list_batch.v1.sh`.

### 7. `outputs/pigean_eaggl_test_v2`

Inferred first-populated time: 2026-04-10 10:14.

This directory contains a one-gene-set PIGEAN-to-EAGGL test run using the first adipose tissue gene set from the no-Harmonizome GTEx aging GMT.

Main outputs include `pigean_eaggl_test.v2.md`, `selected_gene_set.v2.tsv`, `run_summary.v2.tsv`, and the run log. The report records the selected set, PIGEAN mode, EAGGL mode, and explicit EAGGL bundle column mappings used for the test.

Likely entrypoints: `src/run_pigean_eaggl_test.v2.py` and `run/run_pigean_eaggl_test.v2.sh`.

### 8. `outputs/pigean_eaggl_batch_v1`

Inferred first-populated time: 2026-04-10 11:18.

This directory contains dry-run command output for a batch PIGEAN-to-EAGGL workflow across the configured GMT sources. It documents the exact commands that would be run for PIGEAN `beta_tildes` and EAGGL factoring.

Main outputs include `dry_run_commands.v1.md`, `dry_run_commands.v1.tsv`, `source_manifest.v1.tsv`, and the run log. This is primarily a dry-run/documentation output rather than a completed full batch result.

Likely entrypoints: `src/run_pigean_eaggl_batch.v1.py` and `run/run_pigean_eaggl_batch.v1.sh`.

### 9. `outputs/pigean_eaggl_batch_v2`

Inferred first-populated time: 2026-04-10 11:18.

This directory contains the full PIGEAN-to-EAGGL batch run over three GMT sources: the legacy reference, `gtex_harmonizome_analysis_v1`, and `gtex_no_harmonizome_analysis_v1`.

Main outputs include `pigean_eaggl_run_summary.v1.md`, `pigean_eaggl_run_summary.v1.tsv`, `source_manifest.v1.tsv`, and the run log, plus nested per-set PIGEAN/EAGGL outputs. The report indicates 743 total sets, 742 PIGEAN successes, and 688 EAGGL successes.

Likely entrypoints: `src/run_pigean_eaggl_batch.v1.py` and `run/run_pigean_eaggl_batch.v1.sh`.

### 10. `outputs/pigean_eaggl_test_v3`

Inferred first-populated time: 2026-04-13 23:12.

This directory contains a more complete one-gene-set comparison across three sources for `GTEx_AdiposeTissue_20-29_vs_30-39_Up`: the legacy reference GMT, the Harmonizome-mode generated GMT, and the no-Harmonizome generated GMT. It runs PIGEAN and EAGGL, compares gene membership, summarizes factors, and writes plots.

Main outputs include `pigean_eaggl_test.v3.md`, `summary.v1.md`, `factor_summary.v1.tsv`, `factor_similarity.v1.tsv`, `gene_membership.v1.tsv`, `gene_membership_patterns.v1.tsv`, `pairwise_gene_overlap.v1.tsv`, `gene_set_sizes.v1.tsv`, plot PDFs/PNGs, and companion plot markdown files. The report shows low overlap between the legacy set and regenerated sets, higher overlap between the two regenerated sets, and source-specific EAGGL factor results.

Likely entrypoints: `src/run_pigean_eaggl_test.v3.py` and `run/run_pigean_eaggl_test.v3.sh`.

### 11. `outputs/gene_set_comparison_v1`

Inferred first-populated time: 2026-04-13 23:38.

This directory compares gene-set membership across three GMT libraries: the legacy reference GMT, `gtex_harmonizome_analysis_v1`, and `gtex_no_harmonizome_analysis_v1`. It calculates common set names, pairwise overlaps, three-way membership patterns, and summary plots/tables.

Main outputs include `findings_summary.v1.md`, `pairwise_gene_overlap_by_set.v1.tsv`, `pairwise_overlap_summary.v1.tsv`, `triplet_gene_overlap_by_set.v1.tsv`, `gene_membership_patterns_by_set.v1.tsv`, and companion plot files with plot-data TSVs. The analysis found that the two regenerated local GMTs are generally more similar to each other than either is to the legacy reference.

Likely entrypoints: `src/run_gene_set_comparison.v1.py` and `run/run_gene_set_comparison.v1.sh`.

### 12. `outputs/gtex_gene_list_derivation_v1`

Inferred first-populated time: 2026-04-15 12:51.

This directory documents how the gene lists in `gtex_harmonizome_analysis_v1` and `gtex_no_harmonizome_analysis_v1` were derived. It is a documentation-focused analysis rather than a new GMT-generation run.

Main output: `gtex_gene_list_derivation.v1.md`. The report explains the shared GTEx inputs, tissue and age-bin comparison setup, DE processing, and how Harmonizome-mode versus no-Harmonizome postprocessing changes set membership.

### 13. `outputs/gtex_parameter_sweep_v1`

Inferred first-populated time: 2026-04-15 13:08.

This directory contains an early parameter sweep to test whether changing GMT conversion and filtering parameters could make regenerated GTEx gene lists more similar to the legacy GMT.

Main outputs include `parameter_sweep_summary.v1.tsv`, `parameter_sweep_summary.v1.md`, `parameter_effects.v1.tsv`, `parameter_effects.v1.md`, `findings.v1.md`, and the run log. The findings indicate that parameter changes moved set-name coverage and overlap only modestly, with the best configuration still failing to reproduce legacy membership well.

Likely entrypoint: `src/run_gtex_parameter_sweep.v1.py`.

### 14. `outputs/gtex_parameter_sweep_v2`

Inferred first-populated time: 2026-04-15 13:10.

This directory contains a follow-up parameter sweep using the same general goal as `gtex_parameter_sweep_v1`: evaluate whether alternative thresholds or postprocessing choices improve similarity to the legacy GMT.

Main outputs mirror v1: `parameter_sweep_summary.v1.tsv`, `parameter_effects.v1.tsv`, `findings.v1.md`, and the run log. This is a second sweep/output version rather than a separate conceptual analysis.

Likely entrypoint: `src/run_gtex_parameter_sweep.v1.py`.

### 15. `outputs/harmonizome_legacy_gmt_reproduction_plan_v1`

Inferred first-populated time: 2026-04-17 15:28.

This directory contains the planning analysis for reproducing the legacy Harmonizome GTEx aging GMT from the cloned `HarmonizomePythonScripts` repository. It reviews relevant notebooks and identifies the apparent legacy pipeline logic.

Main output: `harmonizome_legacy_gmt_reproduction_plan.v1.md`. The plan identifies the GTEx aging notebook as the most likely source of the legacy GMT logic, including GTEx V8 counts, age-bin comparisons, balanced sampling, limma-voom, adjusted-p-value filtering, sign splitting, and top-250 gene selection.

### 16. `outputs/harmonizome_legacy_gtex_reproduction_v1`

Inferred first-populated time: 2026-04-17 15:40.

This directory contains the standalone reproduction of the Harmonizome legacy GTEx aging-signature workflow. It reconstructs the notebook-style process in a memory-safe script: preparing GTEx metadata, building tissue matrices, selecting mapped genes, running limma/voom per tissue and age comparison, combining DEG tables, generating a legacy-formatted GMT, and comparing to the reference GMT.

Main outputs include `deg_long_combined.v1.tsv`, `gtex_aging_signatures_legacy_format.v1.gmt.gz`, `gtex_aging_signatures_legacy_format.v1.tsv`, `comparison_to_reference.v1.tsv`, `comparison_to_reference.v1.md`, and `run_summary.v1.md`. The latest completed full rerun on 2026-04-20 retained 17,382 samples, 135 comparisons, 28 prepared tissues, 2,515,068 combined DEG rows, and emitted 127 GMT sets. The comparison report indicates 127 shared set names with the 270-set reference, 143 missing reference sets, and 0 extra generated sets.

Likely entrypoints: `src/run_harmonizome_legacy_gtex_reproduction.v1.py`, `src/run_harmonizome_legacy_gtex_reproduction.v2.py`, `run/run_harmonizome_legacy_gtex_reproduction.v1.sh`, and `run/run_harmonizome_legacy_gtex_reproduction.v2.sh`.

### 17. `outputs/r_libs_4.5`

Inferred first-populated time: 2026-04-17 18:07.

This directory is not an analysis result. It is a local R package library used to support the Harmonizome legacy GTEx reproduction and limma/voom runs without requiring a system-wide install.

Installed packages visible in this directory include `BiocManager`, `BiocVersion`, `edgeR`, `limma`, `locfit`, and `statmod`. These support the R-side differential-expression steps in the reproduction workflow.

### 18. `outputs/harmonizome_missing_set_representation_v1`

Inferred first-populated time: 2026-04-17 19:15.

This directory analyzes the 143 legacy reference sets that were missing from the Harmonizome reproduction GMT and asks whether those missing sets were represented in the reproduction inputs.

Main outputs include `missing_set_representation.v1.md`, `missing_set_representation.v1.tsv`, `missing_set_representation_summary.v1.tsv`, and `missing_set_representation_by_tissue.v1.tsv`. The report concludes that all 143 missing sets were represented in prepared inputs, but most failed downstream because the reproduced DE results had zero or fewer than five adjusted-significant genes in the missing direction.

Likely entrypoints: `src/analyze_missing_legacy_set_representation.v1.py` and `run/analyze_missing_legacy_set_representation.v1.sh`.

### 19. `outputs/harmonizome_recovery_sweep_v1`

Inferred first-populated time: 2026-04-17 19:19.

This directory sweeps alternative DE/filtering sensitivity settings using the prepared tissue inputs from the Harmonizome legacy reproduction. The goal is to see whether relaxing filters recovers legacy reference sets that were missing from the baseline reproduction.

Main outputs include `recovery_sweep_summary.v1.tsv`, `recovery_sweep_comparison_details.v1.tsv`, `config_manifest.v1.tsv`, `findings.v1.md`, and the run log. The best reported configuration recovered 18 missing sets relative to the baseline, but overlap with the legacy GMT remained low overall.

Likely entrypoints: `src/run_harmonizome_recovery_sweep.v1.py` and `run/run_harmonizome_recovery_sweep.v1.sh`.

### 20. `outputs/one_missing_legacy_set_analysis_v1`

Inferred first-populated time: 2026-04-20 06:46.

This directory performs a detailed case study for one legacy GMT set that is present in the reference but absent from the reproduction: `GTEx_Blood_20-29_vs_30-39_Up`.

Main outputs include `one_missing_legacy_set_analysis.v1.md`, `selected_missing_set_summary.v1.tsv`, `legacy_gene_status_in_reproduction.v1.tsv`, and DE-ranking tables. The report concludes that the comparison exists in the reproduction input, but no genes pass `adj_p_val < 0.05` in the missing Up direction, so the GMT builder cannot emit that set.

Likely entrypoints: `src/analyze_one_missing_legacy_set.v1.py` and `run/analyze_one_missing_legacy_set.v1.sh`.

### 21. `outputs/shared_low_overlap_gene_set_analysis_v1`

Inferred first-populated time: 2026-04-20 07:32 for the current populated output state.

This directory performs a detailed case study for a set that appears in both the legacy GMT and the reproduction GMT but has low membership overlap: `GTEx_Skin_20-29_vs_60-69_Up`.

Main outputs include `shared_low_overlap_gene_set_analysis.v1.md`, `selected_low_overlap_set_summary.v1.tsv`, `legacy_gene_status_in_reproduction.v1.tsv`, `reproduced_gene_status.v1.tsv`, `shared_genes.v1.tsv`, `legacy_only_genes.v1.tsv`, `reproduced_only_genes.v1.tsv`, `threshold_sweep_legacy_recovery.v1.tsv`, and `legacy_recovery_threshold_summary.v1.tsv`. The latest report shows 16 shared genes out of 250 in each set, Jaccard 0.033058, valid processed Skin identifiers, and no plausible simple threshold adjustment that recovers the legacy set.

Likely entrypoints: `src/analyze_shared_low_overlap_gene_set.v1.py` and `run/analyze_shared_low_overlap_gene_set.v1.sh`.

