# Harmonizome Recovery Sweep v1

## Take-Home Summary

- current_relaxed_sig: recovered_missing_vs_baseline=18, shared_reference_sets=149, generated_sets=149, mean_jaccard=0.056174, median_jaccard=0.050420
- no_filter: recovered_missing_vs_baseline=10, shared_reference_sets=137, generated_sets=137, mean_jaccard=0.059812, median_jaccard=0.052632
- relaxed_filter: recovered_missing_vs_baseline=5, shared_reference_sets=136, generated_sets=136, mean_jaccard=0.065305, median_jaccard=0.057031
- baseline_current: recovered_missing_vs_baseline=0, shared_reference_sets=131, generated_sets=131, mean_jaccard=0.056945, median_jaccard=0.052632
- current_trend_robust: recovered_missing_vs_baseline=0, shared_reference_sets=131, generated_sets=131, mean_jaccard=0.056706, median_jaccard=0.052632

## Interpretation

This sweep reuses the prepared tissue inputs from the legacy-reproduction run and varies only the DE/filtering sensitivity.
Recovery is measured as the number of legacy sets missing from `baseline_current` that appear under an alternative configuration.
