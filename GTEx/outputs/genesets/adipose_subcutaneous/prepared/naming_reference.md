# Naming Reference

This prepared GTEx bundle uses compact age-bin comparison names.

## Comparison Labels

- `age30_20` means `30-39` vs `20-29`
- `age40_20` means `40-49` vs `20-29`
- `age50_20` means `50-59` vs `20-29`
- `age60_20` means `60-69` vs `20-29`
- `age70_20` means `70-79` vs `20-29`

The suffix `_20` always refers to the reference age bin `20-29`.

## Gene Set Labels

Downstream GTEx model runs emit compact gene-set names using:

`<model_id>__<comparison>__<sign>`

Examples:

- `AB1__age50_20__pos`
- `AB1__age50_20__neg`
