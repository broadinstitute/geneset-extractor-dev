# Reproduction contract

`reproduction/reproduce.sh` is executable, uses `set -euo pipefail`, and
supports `--smoke`. It may dispatch existing DIG commands but must not invoke
private helpers or depend on undocumented precomputed intermediates.

`input_manifest.tsv` must include these columns:

```text
input_id  source_uri_or_access_instructions  version_release  checksum
access_method  smoke_full  workflow_stage  redistribution_status
```

Add `committed_fixture` when a small fixture is versioned with the submission.
Every source declared in `submission.yaml` must have a matching input ID.
Checksums can be blank only when infeasible (for example, controlled access);
the source and access instructions still must be explicit.

`expected/output_manifest.tsv` records `output_id`, safe relative path, role,
required flag, model ID, and partition ID. It is a contract for review, not a
generated-output requirement: large biological inputs and generated outputs
must not be committed merely to satisfy validation.

Static checks cannot prove complete dependency tracing, validate scientific
correctness, obtain controlled inputs, execute containers/schedulers, or prove
that external commands have no hidden dependencies. Reviewers must inspect
the rendered commands and source manifests as well.
