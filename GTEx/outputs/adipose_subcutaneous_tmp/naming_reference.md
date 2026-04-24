# Naming Reference

This output bundle uses compact names for age-bin comparisons and emitted gene sets.

## Comparison Labels

- `age30_20` means `30-39` vs `20-29`
- `age40_20` means `40-49` vs `20-29`
- `age50_20` means `50-59` vs `20-29`
- `age60_20` means `60-69` vs `20-29`
- `age70_20` means `70-79` vs `20-29`

In every case, the suffix `_20` refers to the reference age bin `20-29`.

## Gene Set Labels

Gene set names use:

`<model_id>__<comparison>__<sign>`

Examples:

- `M1__age50_20__pos` means the positive-direction gene set from model `M1` for the `50-59` vs `20-29` comparison.
- `M1__age50_20__neg` means the negative-direction gene set from model `M1` for the `50-59` vs `20-29` comparison.

## Directory Names

Per-comparison extractor directories use the comparison label only:

- `extractor/age30_20/`
- `extractor/age40_20/`
- `extractor/age50_20/`
- `extractor/age60_20/`
- `extractor/age70_20/`
