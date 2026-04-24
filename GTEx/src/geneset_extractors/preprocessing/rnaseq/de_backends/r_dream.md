# Vendored Override Note

This file is a GTEx-local vendored override of the upstream
`geneset_extractors.preprocessing.rnaseq.de_backends.r_dream` module.

## Difference From Upstream

The upstream version adds every requested extra covariate that is present in
`sub_meta` to the dream model formula.

This vendored GTEx version is stricter:

1. It keeps only requested extra covariates that are present in `sub_meta`.
2. It then keeps only covariates with at least 2 distinct non-empty,
   non-`NA` values within the comparison subset.
3. It builds the dream formula from
   `.__group + variable_extra_cols + (1|<random_effect_column>)`.

## Reason

For GTEx age-bin comparisons, some requested covariates can be constant within a
subsetted comparison. Passing constant covariates into the dream formula can
create singular or non-informative terms. This override drops those terms
before calling `voomWithDreamWeights` and `dream`.

## Scope

This is intended as a local run-time override for GTEx workflows only. The
upstream `dig-gene-set-extractors` repository remains unchanged.
