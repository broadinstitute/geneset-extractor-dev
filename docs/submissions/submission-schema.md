# `submission.yaml` schema

The versioned JSON Schema is at
[`config/submission_system_v1.schema.json`](../../config/submission_system_v1.schema.json).
`submission.yaml` may be JSON-compatible YAML; ordinary simple YAML mappings
and lists are also accepted without adding a YAML package dependency.

Required top-level concepts are `schema_version`, `library`, `sources`, `dig`,
`configs`, `reproduction`, `expected_outputs`, `environment`, `deviations`, and
`paired_pull_requests`. `library` supplies ID, display name, organism, optional
genome build, assay types, closest pattern, and wrapper directory. `sources`
records name, stable URI/identifier, release, access restriction, and license.
`dig` records its repository, exact commit, and workflow/converter commands.

Use `submission_status: draft` with `dig.commit: TODO` and `TBD` paired PRs
while preparing a change. A `ready` submission requires a lowercase full
40-character DIG commit SHA. PR fields accept `TBD`, `N/A`, or a GitHub pull
request URL.

The config paths must point inside the library to headered model, partition,
and description TSVs. Model IDs must be unique; description and expected-output
records cannot reference unknown model IDs.
