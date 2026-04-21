# GTEx No-Harmonizome Analysis Output v1

- source counts: GTEx Analysis V8 RNASeQC gene reads
- workflow: `geneset_extractors workflows rna_de_prepare --de_mode modern --backend lightweight`
- extractor: `geneset_extractors convert rna_deg_multi --postprocess_mode legacy`
- combined DE table: `/home/ryank/work/geneset_extractors/gtex/outputs/gtex_no_harmonizome_analysis_v1/combined/deg_long_combined.v1.tsv`
- legacy-formatted GMT gzip: `/home/ryank/work/geneset_extractors/gtex/outputs/gtex_no_harmonizome_analysis_v1/gtex_aging_signatures_legacy_format.v1.gmt.gz`

This rerun removes the Harmonizome-specific workflow balancing preset and the Harmonizome-specific extractor postprocessing preset.
