# run_gtex_harmonizome_analysis.v1

Downloads the official adult-GTEx V8 bulk RNA-seq counts and free-access metadata, prepares per-broad-tissue matrices matching the legacy aging-signature tissue set, runs `rna_de_prepare` in harmonizome mode for each tissue, combines the DE outputs, runs `rna_deg_multi`, rewrites GMT names into the legacy `GTEx_<TISSUE>_20-29_vs_<OLDER>_{Up,Down}` style, and writes a comparison summary against the existing reference GMT.

Expected invocation:

```bash
bash run/run_gtex_harmonizome_analysis.v1.sh
```

Key outputs:

- `outputs/gtex_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`
- `outputs/gtex_harmonizome_analysis_v1/rna_deg_multi.v1/`
- `outputs/gtex_harmonizome_analysis_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz`
- `outputs/gtex_harmonizome_analysis_v1/comparison_to_reference.v1.tsv`
