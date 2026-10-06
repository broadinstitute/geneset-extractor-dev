# Collection gene-set reporting

Use the collection reporter to generate individual post-run reports and one
overall report for a set of completed library output roots. It is read-only
with respect to every run root and keeps all generated artifacts under one new
or empty collection output directory.

Create a tab-delimited manifest. `library_id` and `run_root` are required;
paths are relative to the manifest. `generated_gmt` selects one GMT when a run
root has multiple GMTs and a single legacy comparison is desired.

```tsv
library_id\trun_root\tgenerated_gmt\tlegacy_gmt\tname_mapping
GTEx\t../GTEx/outputs/archive\t\t\t
IMPC\t../IMPC/outputs/full\t../IMPC/outputs/full/genesets.gmt\t../../inputs/IMPC/legacy/KOMP2.gmt\t../IMPC/config/legacy_set_mapping.tsv
```

Run:

```bash
bash run/summarize_gene_set_collection.sh \
  --manifest reports/library_runs.tsv \
  --output-dir outputs/postrun_summary/collection_2026-10-06
```

The collection output contains `report.md`, `library_summary.tsv.gz`, optional
`report.pdf`, optional `cross_library_overview.{png,pdf}`, and a `libraries/`
subdirectory containing each library's complete post-run report. PDF assembly
needs the optional `reportlab` module; plot generation needs optional
`matplotlib`. Missing optional modules never prevent table and Markdown output.
