# run_harmonizome_recovery_sweep v1

This workflow runs a focused DE sensitivity sweep to test whether missing legacy GTEx aging sets can be recovered by changing DE-side settings.

Configurations:

- `baseline_current`: current reproduction settings
- `no_filter`: disables `filterByExpr`
- `relaxed_filter`: uses a looser `filterByExpr`
- `current_trend_robust`: keeps current filtering but uses `eBayes(trend=TRUE, robust=TRUE)`
- `current_relaxed_sig`: keeps current DE but relaxes the GMT significance cutoff to `adj_p_val < 0.10`

Inputs:

- prepared tissue input manifest from the completed reproduction run
- reference legacy GMT

Outputs:

- per-config DEG tables and GMTs under `outputs/harmonizome_recovery_sweep_v1/<config_name>/`
- `recovery_sweep_summary.v1.tsv`
- `recovery_sweep_comparison_details.v1.tsv`
- `findings.v1.md`
- `run_harmonizome_recovery_sweep.v1.log`

Usage:

```bash
export R_LIBS_USER=/home/ryank/work/geneset_extractors/gtex/outputs/r_libs_4.5
bash run/run_harmonizome_recovery_sweep.v1.sh
```
