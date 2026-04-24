```bash
/home/ryank/software/miniconda3/envs/work/bin/python3 -m geneset_extractors.cli workflows rna_de_prepare \
  --modality bulk \
  --counts_tsv /home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_matrices/AdiposeTissue.v1.tsv \
  --matrix_orientation gene_by_sample \
  --feature_id_column Name \
  --matrix_gene_symbol_column Description \
  --sample_metadata_tsv /home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_metadata/AdiposeTissue.v1.tsv \
  --sample_id_column sample_id \
  --group_column age_bin \
  --comparisons_tsv /home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/prepared/tissue_comparisons/AdiposeTissue.v1.tsv \
  --covariates sex,smtsd \
  --de_mode harmonizome \
  --balance_seed 1 \
  --backend lightweight \
  --out_dir /home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/rna_de_prepare/AdiposeTissue.v1 \
  --organism human \
  --genome_build hg38
```

