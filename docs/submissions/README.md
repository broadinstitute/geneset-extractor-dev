# New-library submissions

**All substantive data processing and gene-set generation logic belongs in `dig-gene-set-extractors`. `geneset-extractor-dev` may configure, dispatch, execute, refresh, and publish that logic, but must not independently implement it.**

**A submission must include all code necessary to transform the declared source inputs into the final gene sets. Private scripts, undocumented manual transformations, and unexplained precomputed intermediates are not acceptable dependencies.**

Submission tooling is additive and applies only to a library that includes a
`submission.yaml`. Existing libraries remain legacy-compatible and are not
validated by this tool until explicitly adopted.

Run from this repository:

```bash
python3 -m submission_tools scaffold --library-id LIBRARY_X --display-name "Library X" --pattern generic --output LIBRARY_X
python3 -m submission_tools validate --submission LIBRARY_X/submission.yaml
bash run/test_submission_tools.sh
```

Read [architecture.md](architecture.md), [submission-schema.md](submission-schema.md),
[reproduction-contract.md](reproduction-contract.md), and
[review-policy.md](review-policy.md) before filling a scaffold.

See the explicitly non-biological, test-only
[`examples/synthetic_submission`](../../examples/synthetic_submission/README.md)
for a complete small package.
