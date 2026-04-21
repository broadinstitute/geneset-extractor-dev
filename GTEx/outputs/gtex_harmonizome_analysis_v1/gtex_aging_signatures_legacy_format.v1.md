# GTEx Harmonizome Analysis Output v1

- source counts: GTEx Analysis V8 RNASeQC gene reads
- workflow: `geneset_extractors workflows rna_de_prepare --de_mode harmonizome --backend lightweight`
- extractor: `geneset_extractors convert rna_deg_multi`
- combined DE table: `/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`
- legacy-formatted GMT gzip: `/home/ryank/work/geneset_extractors/gtex/outputs/gtex_harmonizome_analysis_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz`

The comparison IDs were emitted as `GTEx_<TISSUE>_20-29_vs_<OLDER_BIN>` while the DE fit kept `group_a=<OLDER_BIN>` and `group_b=20-29`, matching the existing aging-signature naming convention.
