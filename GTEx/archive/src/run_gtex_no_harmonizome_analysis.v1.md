# run_gtex_no_harmonizome_analysis.v1

Re-runs the GTEx V8 aging-signature analysis without Harmonizome-specific settings.

Differences from the Harmonizome run:

- `rna_de_prepare` uses `--de_mode modern`
- `rna_deg_multi` uses `--postprocess_mode legacy`

Outputs are written under `outputs/gtex_no_harmonizome_analysis_v1/`.
