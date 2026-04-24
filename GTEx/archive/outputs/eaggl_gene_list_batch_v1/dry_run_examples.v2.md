# EAGGL Gene-list Batch Dry Run v1

- total_examples: 1

This workflow runs one `eaggl factor` command per input gene set across the configured GMT sources.
The example below shows the first such command in the order the script would run it.

## Example Commands

### 1. eaggl_factor

- explanation: Example set-level EAGGL factoring command. The real run repeats this same structure for every gene set in every source GMT.
- workdir: `/home/ryank/work/geneset_extractors/gtex/pigean`
- example_source: `gtex_harmonizome_analysis_v1`
- example_set_index: `1`
- example_set_name: `GTEx_AdiposeTissue_20-29_vs_30-39_Up`
- example_input_genes: `250`

```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 -m eaggl factor \
  --X-in pigean/bundles/model_small-2026.02.22/data/gene_set_list_msigdb_nohp.txt \
  --gene-list-in outputs/eaggl_gene_list_batch_v1/gtex_harmonizome_analysis_v1/0001_GTEx_AdiposeTissue_20-29_vs_30-39_Up/input_gene_list.v1.txt \
  --gene-list-no-header \
  --factors-out outputs/eaggl_gene_list_batch_v1/gtex_harmonizome_analysis_v1/0001_GTEx_AdiposeTissue_20-29_vs_30-39_Up/factors.v1.tsv \
  --gene-set-clusters-out outputs/eaggl_gene_list_batch_v1/gtex_harmonizome_analysis_v1/0001_GTEx_AdiposeTissue_20-29_vs_30-39_Up/gene_set_clusters.v1.tsv \
  --gene-clusters-out outputs/eaggl_gene_list_batch_v1/gtex_harmonizome_analysis_v1/0001_GTEx_AdiposeTissue_20-29_vs_30-39_Up/gene_clusters.v1.tsv \
  --params-out outputs/eaggl_gene_list_batch_v1/gtex_harmonizome_analysis_v1/0001_GTEx_AdiposeTissue_20-29_vs_30-39_Up/params.v1.tsv
```

