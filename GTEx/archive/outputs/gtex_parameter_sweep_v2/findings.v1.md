# GTEx Parameter Sweep Findings v1

- successful runs: 20
- failed runs: 34
- best run by shared-set coverage then overlap: `legacy_full_top200_logfc_nofilter`
- best run metrics: shared_set_count=262, mean_jaccard=0.128409, median_jaccard=0.104296

## Take-Home Message

Changing converter parameters can move the regenerated library toward the legacy GMT, but only modestly. The baseline legacy-style rerun (`legacy_full_top200_auto_nofilter`) had shared_set_count=262, mean_jaccard=0.046060, and median_jaccard=0.034483.
The best run in this sweep was `legacy_full_top200_logfc_nofilter`, which reached shared_set_count=262, mean_jaccard=0.128409, and median_jaccard=0.104296.
Relative to the baseline, that is a change of shared_set_count=+0 and mean_jaccard=+0.082349.
The Harmonizome preset control remained worse on set-name coverage (shared_set_count=202, mean_jaccard=0.047234), which reinforces that the Harmonizome-style postprocessing is not the right direction if the goal is to mimic the legacy GTEx library.

## Highest-Leverage Parameters

- `score_mode`: best average setting in this sweep was `logfc` (mean mean_jaccard=0.121304, mean shared_set_count=262.00); best single-run setting was `logfc` (max mean_jaccard=0.128409, max shared_set_count=262).
- `gmt_topk_list`: best average setting in this sweep was `300.0` (mean mean_jaccard=0.068782, mean shared_set_count=262.00); best single-run setting was `200.0` (max mean_jaccard=0.128409, max shared_set_count=262).
- `padj_max`: best average setting in this sweep was `none` (mean mean_jaccard=0.063365, mean shared_set_count=236.25); best single-run setting was `none` (max mean_jaccard=0.128409, max shared_set_count=262).
- `min_abs_logfc`: best average setting in this sweep was `none` (mean mean_jaccard=0.063365, mean shared_set_count=236.25); best single-run setting was `none` (max mean_jaccard=0.128409, max shared_set_count=262).
- `gmt_source`: best average setting in this sweep was `full` (mean mean_jaccard=0.069290, mean shared_set_count=258.25); best single-run setting was `full` (max mean_jaccard=0.128409, max shared_set_count=262).

## Top Runs

- `legacy_full_top200_logfc_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc, gmt_topk_list=200.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.128409, median_jaccard=0.104296.
- `legacy_full_top250_logfc_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc, gmt_topk_list=250.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.121404, median_jaccard=0.097696.
- `legacy_full_top300_logfc_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc, gmt_topk_list=300.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.114099, median_jaccard=0.093439.
- `legacy_full_top200_logfc_times_neglog10p_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc_times_neglog10p, gmt_topk_list=200.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.099014, median_jaccard=0.081731.
- `legacy_full_top250_logfc_times_neglog10p_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc_times_neglog10p, gmt_topk_list=250.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.095739, median_jaccard=0.076428.
- `legacy_full_top300_logfc_times_neglog10p_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=logfc_times_neglog10p, gmt_topk_list=300.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.091914, median_jaccard=0.074219.
- `legacy_full_top300_auto_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=auto, gmt_topk_list=300.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.046744, median_jaccard=0.035782.
- `legacy_full_top300_stat_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=stat, gmt_topk_list=300.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.046744, median_jaccard=0.035782.
- `legacy_full_top250_auto_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=auto, gmt_topk_list=250.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.046463, median_jaccard=0.035197.
- `legacy_full_top250_stat_nofilter`: postprocess_mode=legacy, gmt_source=full, score_mode=stat, gmt_topk_list=250.0, padj_max=none, min_abs_logfc=none, shared_set_count=262, mean_jaccard=0.046463, median_jaccard=0.035197.

## Interpretation

The sweep shows that the easiest way to move the regenerated sets toward the legacy GMT is to stay on the legacy-style converter path and tune how the full ranked DEG table is turned into GMT sets. In contrast, switching to selected-gene GMT export or the Harmonizome preset does not recover the legacy library well.
One non-obvious result from the code path is that when `gmt_source=full`, `select` and `top_k` do not determine GMT membership. In that mode, the decisive knobs are the ranking method (`score_mode`), pre-ranking DEG filters (`padj_max`, `min_abs_logfc`), and the emitted set size (`gmt_topk_list`).
