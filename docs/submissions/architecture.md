# Submission architecture

The submission package is a wrapper contract, not a workflow framework. DIG
owns source-data processing, statistics, mapping, converters, gene-set/GMT
generation, metadata, and provenance primitives. This repository owns model
configuration, command dispatch, cluster/container runtime wrappers, metadata
refresh, publication, and the static submission package.

The standard submitted layout is:

```text
LIBRARY_X/
  submission.yaml
  config/
  run/
  src/                         # thin wrapper code only
  tests/fixtures/
  reproduction/
    reproduce.sh
    download_inputs.sh
    input_manifest.tsv
  expected/output_manifest.tsv
```

The archive produced later must preserve the existing output convention:
`genesets/<partition>/models/<model_id>/workflow/` and `extractor/`, including
the existing metadata, provenance, model-sidecar, GMT, and grouped-output
contracts. Submission tooling does not replace DIG's validation or the existing
refresh/publish commands.
