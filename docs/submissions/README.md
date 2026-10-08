# Gene-set library submissions

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

## Convert legacy provenance

This wrapper delegates directly to DIG; it does not rerun models or rebuild
the graph:

```bash
python3 -m submission_tools provenance convert path/to/geneset.provenance.json \
  --metadata path/to/geneset.meta.json --dig-repo ../dig-gene-set-extractors
python3 -m submission_tools provenance convert path/to/outputs --recursive \
  --dig-repo ../dig-gene-set-extractors
```

The batch form discovers sibling metadata and prefers
`geneset.provenance.legacy.json` when both legacy names occur in a directory.

For an Apptainer environment, use the matching launcher. It bind-mounts the
output tree, wrapper checkout, and DIG checkout, then invokes the same native
wrapper command:

```bash
APPTAINER_IMAGE=/path/to/geneset-extractor.sif \
  DIG_REPO=/path/to/dig-gene-set-extractors \
  bash run/convert_provenance_apptainer.sh /path/to/outputs --recursive
```

This is a foreground conversion, not a scheduler array job: `QSUB_BIN`,
`SUBMISSION_ARRAY_MEMORY`, and `SUBMISSION_ARRAY_WALLTIME` intentionally do
not apply. `APPTAINER_BIN`, `APPTAINER_EXTRA_ARGS`, and
`APPTAINER_PYTHON_BIN` are supported. The wrapper location is derived from
the launcher itself, so `REPO_ROOT` is unnecessary.

For large output trees, create and review an array worklist, then submit it:

```bash
APPTAINER_IMAGE=/path/to/geneset-extractor.sif DIG_REPO=/path/to/dig-gene-set-extractors \
  bash run/submit_convert_provenance_apptainer.sh /path/to/outputs
APPTAINER_IMAGE=/path/to/geneset-extractor.sif DIG_REPO=/path/to/dig-gene-set-extractors \
  bash run/submit_convert_provenance_apptainer.sh /path/to/outputs --submit
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
migrate them into the same contract. For local Codex authoring with remote full
reproduction, follow [remote-adoption-execution.md](remote-adoption-execution.md).
Maintainers adopting a trusted existing
submission should use the complete
[trusted-adoption tutorial](adopting-trusted-existing-submission.md).

For a brand-new source library, use the isolated
[creating-new-library workflow](creating-new-library.md). It creates a fresh
two-repository workspace and provides `./verify-library` and
`./submit-library` helpers that use the workspace-local tooling.

For documented external releases that provide precomputed GMTs but not complete
regeneration code, use [the external GMT import workflow](importing-external-precomputed-gmts.md).

See the explicitly non-biological, test-only
[`examples/synthetic_submission`](../../examples/synthetic_submission/README.md)
for a complete small package.
