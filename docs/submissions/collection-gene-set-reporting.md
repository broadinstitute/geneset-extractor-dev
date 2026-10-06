# Collection gene-set reporting

Use the collection reporter to generate individual post-run reports and one
overall report for a set of completed library output roots. It is read-only
with respect to every run root and keeps all generated artifacts under one new
or empty collection output directory.

Create a tab-delimited pair manifest. `library_id`, `model_id`, `legacy_gmt`,
and `current_gmt` are required; paths are relative to the manifest.
`name_mapping` is optional and maps renamed gene sets *within* a GMT pair.

```tsv
library_id\tmodel_id\tlegacy_gmt\tcurrent_gmt\tname_mapping
GTEx\tM1\t../../legacy_gmts/GTEx/GTEx_XMT_2023-03-10_GTEx_Tissues_V8_2023.gmt\t../GTEx/outputs/compiled/M1.genesets.gmt\t
IMPC\tHZ1\t../../legacy_gmts/IMPC/KOMP2_XMT_2022-12-13_KOMP2_Mouse_Phenotypes_2022.gmt\t../IMPC/outputs/full/genesets.gmt\t../IMPC/adoption/legacy_reference_mapping.tsv
```

Run:

```bash
bash run/summarize_gene_set_collection.sh \
  --manifest reports/library_runs.tsv \
  --output-dir outputs/postrun_summary/collection_2026-10-06
```

The collection output contains `report.md`, `library_summary.tsv.gz`,
`pair_summary.tsv.gz`, optional `report.pdf`, optional
`cross_library_overview.{png,pdf}`, and a `pairs/<library>/<model>/`
subdirectory containing each pair's complete post-run report. PDF assembly
needs the optional `reportlab` module; plot generation needs optional
`matplotlib`. Missing optional modules never prevent table and Markdown output.
