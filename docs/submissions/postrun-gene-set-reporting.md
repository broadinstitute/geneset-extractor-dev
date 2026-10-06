# Post-run gene-set reporting

`submission_tools.postrun_report` is a wrapper-side, read-only reporter for
completed GMT outputs. It discovers GMTs under a run root, summarizes their
content and layout, and can compare one legacy GMT to each selected generated
GMT. It does not alter generated outputs and does not participate in gene-set
construction.

Run it through the explicit wrapper:

```bash
bash run/summarize_genesets.sh \
  --run-root GTEx/outputs/archive \
  --output-dir GTEx/outputs/postrun_summary/2026-10-06
```

To compare legacy outputs, either select one generated GMT or provide one
`--legacy-gmt` per selected/generated GMT in the same order. Requiring equal
counts prevents a legacy file from being compared to an arbitrary discovered
output.

```bash
bash run/summarize_genesets.sh \
  --run-root IMPC/outputs/full \
  --gmt IMPC/outputs/full/genesets.gmt \
  --legacy-gmt inputs/IMPC/legacy/KOMP2.gmt \
  --output-dir IMPC/outputs/postrun_summary/full_vs_legacy
```

When gene-set names changed, pass `--name-mapping mapping.tsv`. The tabular
mapping must have `legacy_set_name` and `generated_set_name` columns and be
one-to-one. Its declared pairs are written to `legacy_set_mapping_audit.tsv.gz`.

The report directory must be new or empty. It contains `report.md`, gzipped TSV
tables, the executed command, a log, and a manifest. Tables include GMT and
gene-set inventory, QC flags, and—when requested—legacy summary/per-set
comparison statistics. Plots are written as PNG and PDF when the optional
`matplotlib` module is available; reporting otherwise completes and records
that plots were skipped. A combined `report.pdf` containing report tables and
available plots is written when the optional `reportlab` module is available;
it likewise never prevents the Markdown/TSV report from completing.

Comparison is by exact gene-set name (or the supplied explicit mapping) and set
membership. Duplicate names are
warnings and later duplicate records are excluded rather than merged. Changed
set names are never guessed.
