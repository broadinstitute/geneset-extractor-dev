# Planning Provenance

These are the original inspection commands used to derive the age-binned model planning artifacts.

```bash
sed -n '1,220p' GTEx_model_plan.txt
find dig-gene-set-extractors/src/geneset_extractors -maxdepth 4 -type f | sort | rg 'rna|cli'
find geneset-extractor-dev/GTEx -maxdepth 3 \( -path 'geneset-extractor-dev/GTEx/archive' -o -path 'geneset-extractor-dev/GTEx/archive/*' \) -prune -o -type d -print | sort
sed -n '1,260p' dig-gene-set-extractors/docs/assays/rnaseq/de_workflow.md
sed -n '1,320p' dig-gene-set-extractors/docs/assays/rnaseq/guide.md
sed -n '1,260p' dig-gene-set-extractors/src/geneset_extractors/extractors/converters/specs/rna_deg_multi.json
rg -n "de_mode|backend auto|balance|gene_filter_scope|covariates|postprocess_mode|score_mode|gmt_source|gmt_topk_list|emit_small_gene_sets|disable_default_excludes|gmt_biotype_allowlist" dig-gene-set-extractors/src/geneset_extractors/{workflows,preprocessing,extractors,cli.py} -g '*.py'
sed -n '560,760p' dig-gene-set-extractors/src/geneset_extractors/preprocessing/rnaseq/de_prepare.py
sed -n '1,260p' dig-gene-set-extractors/src/geneset_extractors/extractors/converters/rna_deg_multi.py
sed -n '240,420p' dig-gene-set-extractors/src/geneset_extractors/extractors/rnaseq/deg_scoring.py
sed -n '1,220p' dig-gene-set-extractors/src/geneset_extractors/preprocessing/rnaseq/de_backends/r_limma_voom.py
sed -n '220,360p' dig-gene-set-extractors/src/geneset_extractors/extractors/rnaseq/deg_workflow.py
sed -n '360,430p' dig-gene-set-extractors/src/geneset_extractors/preprocessing/rnaseq/de_prepare.py
```

External verification used for the release target:

- GTEx portal downloads page named in the plan
- Adult GTEx v10 file index pages for the current bulk gene-reads file and counts-by-tissue collection
