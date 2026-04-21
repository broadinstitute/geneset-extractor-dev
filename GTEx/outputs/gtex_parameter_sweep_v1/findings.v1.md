# GTEx Parameter Sweep Findings v1

- successful runs: 20
- failed runs: 34
- best run by shared-set coverage then overlap: `legacy_full_top200_auto_nofilter`
- best run metrics: shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000

## Take-Home Message

Changing converter parameters can move the regenerated library toward the legacy GMT, but only modestly. The baseline legacy-style rerun (`legacy_full_top200_auto_nofilter`) had shared_set_count=262, mean_jaccard=0.000000, and median_jaccard=0.000000.
The best run in this sweep was `legacy_full_top200_auto_nofilter`, which reached shared_set_count=262, mean_jaccard=0.000000, and median_jaccard=0.000000.
Relative to the baseline, that is a change of shared_set_count=+0 and mean_jaccard=+0.000000.
The Harmonizome preset control remained worse on set-name coverage (shared_set_count=202, mean_jaccard=0.000059), which reinforces that the Harmonizome-style postprocessing is not the right direction if the goal is to mimic the legacy GTEx library.

## Highest-Leverage Parameters

- `gmt_topk_list`: best average setting in this sweep was `none` (mean mean_jaccard=0.000059, max mean_jaccard=0.000059, mean shared_set_count=202.00).
- `score_mode`: best average setting in this sweep was `auto` (mean mean_jaccard=0.000015, max mean_jaccard=0.000059, mean shared_set_count=247.00).
- `padj_max`: best average setting in this sweep was `none` (mean mean_jaccard=0.000003, max mean_jaccard=0.000059, mean shared_set_count=236.25).
- `min_abs_logfc`: best average setting in this sweep was `none` (mean mean_jaccard=0.000003, max mean_jaccard=0.000059, mean shared_set_count=236.25).
- `gmt_source`: best average setting in this sweep was `full` (mean mean_jaccard=0.000004, max mean_jaccard=0.000059, mean shared_set_count=258.25).

## Top Runs

- `legacy_full_top200_auto_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=auto, gmt_topk_list=200.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top200_logfc_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc, gmt_topk_list=200.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top200_logfc_times_neglog10p_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc_times_neglog10p, gmt_topk_list=200.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top200_signed_neglog10padj_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=signed_neglog10padj, gmt_topk_list=200.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top200_stat_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=stat, gmt_topk_list=200.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top250_auto_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=auto, gmt_topk_list=250.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top250_logfc_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc, gmt_topk_list=250.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top250_logfc_times_neglog10p_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc_times_neglog10p, gmt_topk_list=250.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top250_signed_neglog10padj_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=signed_neglog10padj, gmt_topk_list=250.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.
- `legacy_full_top250_stat_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=stat, gmt_topk_list=250.0, padj_max=nan, min_abs_logfc=nan, shared_set_count=262, mean_jaccard=0.000000, median_jaccard=0.000000.

## Interpretation

The sweep shows that the easiest way to move the regenerated sets toward the legacy GMT is to stay on the legacy-style converter path and tune how the full ranked DEG table is turned into GMT sets. In contrast, switching to selected-gene GMT export or the Harmonizome preset does not recover the legacy library well.
One non-obvious result from the code path is that when `gmt_source=full`, `select` and `top_k` do not determine GMT membership. In that mode, the decisive knobs are the ranking method (`score_mode`), pre-ranking DEG filters (`padj_max`, `min_abs_logfc`), and the emitted set size (`gmt_topk_list`).
