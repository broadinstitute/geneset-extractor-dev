# Missing Legacy Set Representation v1

## Take-Home Summary

- missing legacy sets examined: 143
- represented in prepared reproduction input: 143
- absent from prepared reproduction input: 0
- present in input but with zero significant genes in the missing direction: 122
- present in input but with only 1-4 significant genes in the missing direction: 21
- present in input with >=5 significant genes in the missing direction but still absent from GMT: 0

## Interpretation

This analysis asks whether the missing legacy GMT sets were even represented as tissue/age comparisons in the reproduction input.
A set is counted as represented when its comparison_id appears in the prepared comparison manifest, meaning the GTEx input had enough samples to define that contrast.
If a comparison was represented but the set is still missing, the missing direction usually failed downstream because there were either no significant genes or fewer than 5 significant genes after `adj.P.Val < 0.05` filtering.

## Top Missing-Set Status Counts

- comparison_present_no_significant_genes_in_direction: 122 missing sets (represented_in_input=true)
- comparison_present_but_fewer_than_5_significant_genes_in_direction: 21 missing sets (represented_in_input=true)

## Most Affected Tissues

- Pituitary / comparison_present_no_significant_genes_in_direction: 10
- Vagina / comparison_present_no_significant_genes_in_direction: 10
- Kidney / comparison_present_no_significant_genes_in_direction: 9
- Liver / comparison_present_no_significant_genes_in_direction: 8
- Spleen / comparison_present_no_significant_genes_in_direction: 7
- AdrenalGland / comparison_present_no_significant_genes_in_direction: 6
- Blood / comparison_present_no_significant_genes_in_direction: 6
- Pancreas / comparison_present_no_significant_genes_in_direction: 6
- Prostate / comparison_present_no_significant_genes_in_direction: 6
- SmallIntestine / comparison_present_no_significant_genes_in_direction: 6
- Stomach / comparison_present_no_significant_genes_in_direction: 6
- Ovary / comparison_present_no_significant_genes_in_direction: 5
- Bladder / comparison_present_no_significant_genes_in_direction: 4
- Breast / comparison_present_no_significant_genes_in_direction: 4
- SalivaryGland / comparison_present_no_significant_genes_in_direction: 4
