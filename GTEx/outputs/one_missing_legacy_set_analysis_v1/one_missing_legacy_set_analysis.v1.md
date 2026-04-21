# One Missing Legacy Gene Set Analysis v1

## Take-Home Summary

The selected set is `GTEx_Blood_20-29_vs_30-39_Up`. It appears in the legacy GMT with 250 genes but does not appear in the reproduction GMT.
The underlying comparison `GTEx_Blood_20-29_vs_30-39` is represented in the reproduction input: Blood has 85 raw `20-29` samples and 80 raw `30-39` samples, which were balanced to 80 and 80 samples respectively.
The reason the set is missing is downstream DE filtering: the reproduction DE table contains 14861 tested genes for this comparison, but 0 genes pass `adj_p_val < 0.05` in any direction and 0 pass in the missing `Up` direction.
Because the GMT builder emits only direction-specific groups with at least 5 significant genes, this set cannot be emitted from the reproduced DE results.

## Input Representation

- tissue_name: `Blood`
- older age bin: `30-39`
- raw `20-29` sample count: 85
- raw older-bin sample count: 80
- balanced `20-29` sample count used for DE: 80
- balanced older-bin sample count used for DE: 80

## DE Evidence

- reproduced DEG rows for this comparison: 14861
- reproduced genes with `adj_p_val < 0.05`: 0
- reproduced genes with `adj_p_val < 0.05` and `Up` logFC sign: 0
- minimum reproduced adjusted p-value: 0.999778
- legacy genes present in reproduced DEG table: 135 of 250
- legacy genes with same reproduced logFC direction: 135 of 250
- legacy genes significant in reproduced DEG table: 0 of 250

## Interpretation

This is not an input-coverage problem. The Blood `20-29` versus `30-39` comparison exists and was tested in the reproduction.
It is missing because the reproduced limma/voom results do not contain enough adjusted-significant genes in the `Up` direction to pass the GMT emission rule.
The legacy GMT therefore appears to have been generated under DE, filtering, mapping, or significance behavior that produced a much stronger signal for this comparison than the current reproduction.

## Output Files

- `selected_missing_set_summary.v1.tsv`
- `legacy_gene_status_in_reproduction.v1.tsv`
- `legacy_genes_in_reproduction_by_adj_p_val.v1.tsv`
- `top_reproduction_genes_by_adj_p_val.v1.tsv`
- `top_reproduction_genes_in_missing_direction.v1.tsv`
