# AMP-AD / AD Knowledge Portal Bulk Brain RNA

This wrapper integrates the AD Knowledge Portal AMP-AD released bulk-brain RNA
differential-expression summary table.

Input data is expected outside committed source, for example:

```text
working_data/differentialExpressionSummary.tsv
```

The released file is already an analysis table, not raw expression data. The
wrapper therefore does not refit differential expression. It writes a stable
`comparison_id` from:

```text
Study + Tissue + Model + Comparison + Sex
```

and delegates gene-set extraction to `dig-gene-set-extractors` via:

```text
geneset_extractors.cli convert rna_deg_multi
```

This keeps DIG as the owner of the RNA DEG conversion logic while keeping this
repo as the library-specific orchestration layer.
