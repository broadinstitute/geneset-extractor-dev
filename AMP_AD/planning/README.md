# AMP-AD / AD Knowledge Portal Bulk Brain RNA

This wrapper integrates the AD Knowledge Portal AMP-AD released bulk-brain RNA
differential-expression summary table.

Input data is expected outside committed source, for example:

```text
working_data/differentialExpressionSummary.tsv
```

The released file is already an analysis table, not raw expression data. The
wrapper therefore does not refit differential expression. AMP-AD-specific
preparation is owned by DIG through:

```text
geneset_extractors.cli workflows amp_ad_released_dea
```

That workflow writes a stable `comparison_id` from:

```text
Study + Tissue + Model + Comparison + Sex
```

and emits the prepared long-form DEG table plus upstream provenance rooted in
the released input table. The wrapper then delegates gene-set extraction to
`dig-gene-set-extractors` via:

```text
geneset_extractors.cli convert rna_deg_multi
```

This keeps DIG as the owner of both the AMP-AD preparation workflow and RNA DEG
conversion logic while keeping this repo as the library-specific orchestration
layer.
