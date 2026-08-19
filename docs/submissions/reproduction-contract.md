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

When one manifest contains outputs with different provenance-sidecar
conventions, scope a provenance contract to the roles that actually have its
declared sidecar:

```yaml
provenance:
  contracts:
    - scope: full
      output_manifest: expected/output_manifest.tsv
      provenance_filename: geneset.provenance.json
      artifact_roles: [extractor_gmt]
```

For example, a DIG workflow graph may be upstream evidence in an extractor
sidecar; it does not imply that the workflow output has a separate
`geneset.provenance.json` beside it.

Static checks cannot prove complete dependency tracing, validate scientific
correctness, obtain controlled inputs, execute containers/schedulers, or prove
that external commands have no hidden dependencies. Reviewers must inspect
the rendered commands and source manifests as well.

`run_receipt.json` records wrapper/DIG commits, schema version, input/output
manifest digests, environment identifier/digest, command, timestamps, expected
and completed models, and validation result. It does not cryptographically
prove reproducibility.

## Source URLs versus local execution paths

Use `config/provenance_overlay.json` to provide stable source identifiers,
canonical URIs, and public download URLs for declared input-manifest records.
The overlay is passed to a supporting DIG entry point with
`--provenance_overlay_json`. Do not rewrite `$HOME`, `~`, an adoption
workspace, a wrapper root, or an output directory to a source-provider URL
with `--provenance_mirror_local_prefix`: it would falsely present local
commands and generated outputs as remote source data. A narrowly defined
local cache mirror is permitted only when it maps declared inputs to their
actual stable source location.

## Provenance completeness

`./verify-adoption` and `./verify-library` run a `provenance_complete` stage
after local smoke reproduction. It checks each declared sidecar for valid JSON,
unique nodes, valid edges, a source-input → operation → geneset path, and a
materialized expected artifact. It also checks declared input-manifest linkage
and contributor-specific paths. The stage records `smoke` and `full` status in
the workspace manifest and receipt.

Draft submissions may report incomplete unavailable full provenance as a
warning. For ready submissions, missing required provenance, incomplete graph
linkage, or external source files without stable identifiers are errors. Local
paths for generated outputs and recorded execution commands are permitted;
they are not falsely treated as source locations. These checks validate
declared structure and provenance linkage; they do not prove scientific
correctness or cryptographically prove reproducibility.
