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

CI uses the required check named **`validate-new-library-submissions`**. It
runs the same dependency-free unit and scaffold/integration tests, validates
the committed synthetic example, discovers changed directories exclusively by
`submission.yaml`, and validates those discovered packages. Reproduce a CI
failure locally with `bash run/test_submission_tools.sh`, then run
`python3 -m submission_tools validate --submission <directory>` for the
reported package. CI never downloads biological data or runs Docker,
Apptainer, S3, scheduler, or controlled-access workflows.

For ready submissions, CI checks out only the allowlisted DIG repository at
the full SHA declared in `submission.yaml`, then runs low-cost DIG checks. It
uses `pull_request` (never `pull_request_target`), read-only permissions, and
no secrets; it never runs submission download or reproduction scripts.

Read [architecture.md](architecture.md), [submission-schema.md](submission-schema.md),
[reproduction-contract.md](reproduction-contract.md), and
[review-policy.md](review-policy.md) before filling a scaffold. Contributors
should start with [contributor-workflow.md](contributor-workflow.md), including
the proposal issue and paired-PR sequence.

If gene sets already exist outside this framework, follow
[adopting-existing-library.md](adopting-existing-library.md) to inventory and
migrate them into the same contract.

For a brand-new source library, use the isolated
[creating-new-library workflow](creating-new-library.md). It creates a fresh
two-repository workspace and provides `./verify-library` and
`./submit-library` helpers that use the workspace-local tooling.

See the explicitly non-biological, test-only
[`examples/synthetic_submission`](../../examples/synthetic_submission/README.md)
for a complete small package.
