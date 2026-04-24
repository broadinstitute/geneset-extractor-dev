# run_eaggl_gene_list_batch.v1

Parses three GTEx aging GMT sources and runs EAGGL standalone gene-list enrichment (`python -m eaggl factor`, workflow `F2`) once per GMT row against the local `pigean/tests/data/model_small/gene_set_list_mouse_2024.txt` panel.

Outputs:

- `outputs/eaggl_gene_list_batch_v1/source_manifest.v1.tsv`
- `outputs/eaggl_gene_list_batch_v1/eaggl_run_summary.v1.tsv`
- `outputs/eaggl_gene_list_batch_v1/eaggl_run_summary.v1.md`
- per-set subdirectories with input gene list, stdout/stderr logs, and any emitted EAGGL factor outputs
