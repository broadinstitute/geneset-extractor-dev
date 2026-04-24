# Vendored Override Note

This file is a GTEx-local vendored override of the upstream
`geneset_extractors.preprocessing.rnaseq.de_backends.r_limma_voom` module.

## Difference From Upstream

The upstream version adds every requested extra covariate that is present in
`sub_meta` to the limma/voom design matrix.

This vendored GTEx version is stricter:

1. It keeps only requested extra covariates that are present in `sub_meta`.
2. It then keeps only covariates with at least 2 distinct non-empty,
   non-`NA` values within the comparison subset.
3. It builds the design matrix from `.__group + variable_extra_cols`.

## Reason

For GTEx age-bin comparisons, some requested covariates can be constant within a
subsetted comparison. Passing constant covariates into the R design can create
singular or non-informative terms. This override drops those terms before
calling `model.matrix`, `voom`, and `lmFit`.

## Scope

This is intended as a local run-time override for GTEx workflows only. The
upstream `dig-gene-set-extractors` repository remains unchanged.
