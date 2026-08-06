# Submission System v1: Implementation Plan

## Status and scope

This is a design-only, additive plan.  It deliberately does **not** migrate GTEx,
MoTrPAC, HuBMAP, or LINCS_L1000; alter their output formats; rename an existing
command; or change their runtime behavior.  The first implementation uses the
four existing libraries as compatibility fixtures and is opt-in for a new
library or an explicitly requested per-library adoption.

The two repositories inspected are both clean and are currently checked out at
`rk-submission-system-v1`.

## Current architecture and evidence

### DIG: processing and reusable output contract

`dig-gene-set-extractors` is a Python package (`pyproject.toml`) with package
entry points `geneset-extractors` and `geneset_extractors`, both mapped to
`geneset_extractors.cli:main`.  It owns the substantive layer:

- generic converters under `src/geneset_extractors/extractors/converters/`;
- assay and library workflows under `src/geneset_extractors/workflows/`,
  including `gtex_*`, `motrpac_*`, `hubmap_*`, and `lincs_l1000_*`;
- reusable RNA, mapping, scoring, GMT, metadata, provenance, validation, and
  resource code under `preprocessing/`, `core/`, and `io/`;
- JSON schemas for `geneset.meta.json` and `geneset.provenance.json`;
- a test suite covering CLI smoke behavior, validation, metadata/provenance,
  workflow behavior, converters, and compatibility.

The existing public CLI namespaces that submission v1 must call, never replace,
are:

```text
geneset-extractors workflows <workflow>
geneset-extractors convert <converter>
geneset-extractors validate <output_dir>
geneset-extractors metadata patch <geneset.meta.json> ...
geneset-extractors provenance build <geneset.meta.json> ...
geneset-extractors resources ...
```

`geneset-extractors validate` already accepts both a single final output and a
grouped directory, and validates metadata against the packaged schema.
`write_metadata()` creates `geneset.provenance.json` beside
`geneset.meta.json`, and provenance supports upstream workflow graphs plus
local-to-remote path mirroring.  These are the authoritative final-artifact
mechanisms; submission v1 must not reimplement them.

The DIG GitHub Actions workflow (`.github/workflows/tests.yml`) presently runs
`pytest -q`, builds a wheel, installs that wheel into a fresh virtualenv, and
smoke-tests `omics2geneset list` and `omics2geneset describe atac_bulk`.

### Wrapper repository: library execution and publishing

`geneset-extractor-dev` is the orchestration layer.  Its onboarding documents
explicitly require primary workflow/converter/provenance logic to live in DIG,
and describe the wrapper repository as owning configs, worklists, model
selection, cluster and Apptainer launch, refresh, and publication.

The four reference structures are consistent at the top level:

```text
<library>/config/     model lists, model manifests, description templates,
                      and a partition list where needed
<library>/src/        Python model dispatch and thin integration wrappers
<library>/run/        local wrapper entrypoint(s)
<library>/planning/   documentation/proposals where useful
```

- **GTEx** is tissue partitioned and has age-binned and continuous-age
  manifests, `tissue_list.tsv`/`broad_tissue_list.tsv`, and grouped extractor
  results.
- **MoTrPAC** is tissue partitioned and uses model families for training,
  timewise/timepoint, released DEA, and raw aggregation.
- **HuBMAP** uses model lists/manifests and an `all_signatures`-style released
  ASCT+B workflow.
- **LINCS_L1000** uses model lists/manifests and separate chemical-perturbation
  and CRISPR-knockout workflow paths converging on the same final contract.

The shared runtime conventions to preserve are:

```text
<run_root>/<library>_all_models/
  genesets/<partition>/models/<model_id>/
    workflow/
    extractor/
      [<group>/]genesets.gmt
      [<group>/]geneset.meta.json
      [<group>/]geneset.provenance.json
      geneset.model.json
      manifest.tsv                 # when output is grouped
```

Existing output trees also retain `run.log`, command records, workflow
comparison manifests, and summary files.  The grouping level is library/model
specific and must not be flattened by submission v1.

The generic wrapper commands to reuse are:

```text
bash run/refresh_model_metadata_and_provenance.sh \
  --model_id <id> --model_dir <path> --description_template_tsv <path> \
  --dig_dir <dig-gene-set-extractors> [...]

bash run/publish_library_to_s3.sh \
  --local_output_root <run-root> --s3_output_root s3://... \
  [--model_id id[,id...]] [--provenance_only_outputs] [--dry_run]
```

The existing Apptainer submit wrappers set `PYTHONPATH=<DIG>/src` and invoke
the library-specific wrapper, with model-only and refresh modes.  The existing
publisher accepts `--model_id`, `--manifest_out`, `--path_map_out`,
`--provenance_only_outputs`, `--dry_run`, and guarded overwrite options.  The
new system must compose these commands rather than duplicate S3, provenance,
or metadata logic.

There is no `geneset-extractor-dev/.github/workflows/` directory today.  The
new CI therefore needs to be additive and must not assume that existing
libraries can be run in GitHub Actions with their private/large inputs.

## Ownership decisions

| Component | Owner | Rationale |
| --- | --- | --- |
| Workflow, statistics, gene/feature mapping, converter, gene-set/GMT generation | DIG | It is assay logic and must remain reusable. |
| Metadata/provenance schema validation for final extractor artifacts | DIG | It extends the existing schema/`validate` contract. |
| Submission manifest structural validation and digest computation | DIG | This is reusable, library-agnostic correctness logic. |
| Library configs, model enumeration, worklist generation, command rendering, scheduler/Apptainer invocation | dev | These are environment- and library-orchestration concerns. |
| Submission assembly manifest, archive staging, refresh and publish orchestration | dev | It is deployment/publishing policy and composes existing wrappers. |
| S3 publication mechanics | existing dev publisher | Do not duplicate or replace it. |

In particular, submission v1 will not place workflow code, statistical
validation, gene mapping, or GMT construction in `geneset-extractor-dev`.

## Proposed additive files

### `dig-gene-set-extractors`

```text
src/geneset_extractors/
  core/
    submission.py
  schemas/
    submission_manifest.schema.json
  cli.py                         # additive `submission validate` registration only
tests/
  test_submission_manifest.py
  test_submission_cli.py
docs/
  submission_system_v1.md
```

`core/submission.py` will be pure, standard-library-oriented reusable logic:
parse a manifest, validate its schema and cross-file invariants, walk declared
model directories safely, call the existing output-directory validator, and
calculate stable SHA-256/size records.  It will not execute workflows, invoke
the scheduler, upload files, patch metadata, or make biological judgments.

Add exactly one new CLI surface:

```bash
geneset-extractors submission validate \
  --manifest /path/to/submission.manifest.json \
  --root /path/to/staged-submission \
  [--check-files] [--json-report /path/to/report.json]
```

Existing CLI names and argument behavior remain unchanged.  `--check-files`
performs the full artifact checks; without it the command validates manifest
shape and safe relative paths only.  A separate command, rather than new
semantics in `geneset-extractors validate`, avoids changing current behavior.

### `geneset-extractor-dev`

```text
config/
  submission_system_v1.schema.json
src/
  submission_system_v1.py
run/
  submission_system_v1.sh
  submission_system_v1_apptainer.sh
docs/dev/submission_system_v1.md
tests/
  test_submission_system_v1.py
  fixtures/submission_system_v1/
    minimal_submission.manifest.json
    invalid_submission.manifest.json
.github/workflows/submission-system-v1.yml
```

`submission_system_v1.py` is a thin CLI orchestrator.  It reads a declarative
library submission configuration, performs no biological transformation, and
only renders worklists/commands, stages an archive tree, writes the wrapper
manifest, delegates validation to DIG, and optionally calls the existing
refresh/publish scripts.  It must use explicit paths and subprocess argument
lists, not shell interpolation.

The shell wrappers only locate the sibling repositories, choose the Python or
Apptainer runtime, bind explicit input/output paths for Apptainer, and invoke
the Python entrypoint.  They follow the existing `run/*_apptainer.sh` pattern.

No existing `GTEx/`, `MoTrPAC/`, `HuBMAP/`, or `LINCS_L1000/` files are part of
the first implementation.  Their adoption is an explicit later phase and will
be one library per change set.

## Submission configuration and manifest design

### Input configuration (dev-owned)

Each new/adopting library adds, only when opted in:

```text
<library>/config/submission_system_v1.tsv
```

It has one headered row per supported model/partition command.  Required
columns are:

```text
library_id  model_id  partition_id  enabled  submit_wrapper
run_root_template  model_dir_template  description_template_tsv
```

Optional columns are `model_family`, `submit_args_json`, `apttainer_wrapper`,
`input_profile`, `expected_output_mode` (`single` or `grouped`), and
`publish_default`.  `model_id`, `partition_id`, and templates must resolve to
the existing `genesets/<partition>/models/<model_id>` convention.  The new
configuration references existing `model_list.tsv`, `model_manifest.tsv`,
partition lists, and description templates; it does not duplicate their model
parameters or redefine a model.

The top-level `config/submission_system_v1.schema.json` documents and
validates this TSV-derived record shape.  It intentionally does not prescribe
assay parameters because those remain in existing library manifests and DIG
workflow flags.

### Archive manifest (written by dev, validated by DIG)

The staged archive contains `submission.manifest.json`, with only
forward-slash, relative paths.  Required top-level fields:

```json
{
  "schema_version": "1.0.0",
  "submission_id": "<stable user-supplied identifier>",
  "library_id": "<library>",
  "created_at": "<UTC ISO-8601 timestamp>",
  "producer": {
    "dev_git_commit": "<commit-or-unknown>",
    "dig_git_commit": "<commit-or-unknown>",
    "command": ["..."]
  },
  "models": [],
  "files": []
}
```

Each `models[]` item records stable `model_id`, `partition_id`, optional
`model_family`, a relative `model_dir`, `output_mode`, and relative references
to its `workflow/`, `extractor/`, and `geneset.model.json`.  Each `files[]`
item records `path`, `sha256`, `size_bytes`, `role`, and optional `model_id` /
`partition_id`.  Roles include `workflow_artifact`, `extractor_artifact`,
`model_sidecar`, `metadata`, `provenance`, `gmt`, `group_manifest`, `log`, and
`command_record`.

The manifest does not embed raw inputs, credentials, environment variables,
absolute paths, S3 destinations, or a second copy of metadata/provenance.
Those remain in existing provenance graphs and the existing publication
configuration.  Sorted models/files and canonical JSON serialization make the
manifest deterministic except for the explicit timestamp.

## Scaffold command

The dev command is intentionally an opt-in generator for a **new** library
directory, never a mutator of an existing library by default:

```bash
python3 geneset-extractor-dev/src/submission_system_v1.py scaffold \
  --library-id LIBRARY_X \
  --destination geneset-extractor-dev/LIBRARY_X \
  --partition-kind tissue
```

It fails if the destination exists unless `--force-empty-directory` is given;
that option only permits an empty directory and never overwrites a file.  It
creates the standard `config/`, `src/`, `run/`, and `planning/` layout, headered
empty `model_list.tsv`, `model_manifest.tsv`, `model_description_templates.tsv`,
and partition TSV, a commented `submission_system_v1.tsv`, plus thin wrapper
templates.  The generated wrapper commands point to DIG CLI namespaces and
contain TODO values; they are not runnable analysis implementations.

For an existing library, the explicit, non-generating command is:

```bash
python3 geneset-extractor-dev/src/submission_system_v1.py init-config \
  --library-root geneset-extractor-dev/GTEx --dry-run
```

It prints the proposed configuration and changes nothing until a later,
separately authorized implementation change.  This avoids implicit migration.

## Validator design

Validation is layered and fail-closed:

1. **Configuration validation (dev):** header/required values, unique
   `(library_id, partition_id, model_id)`, `enabled` boolean, a declared
   existing model in the referenced `model_list.tsv`, safe templates, and a
   readable description-template mapping for each selected model.
2. **Manifest validation (DIG):** JSON schema, schema version, exact relative
   path normalization, no duplicate model key/file path, no `..`, no symlink
   escape, SHA-256 format, non-negative size, and model/file cross references.
3. **Artifact validation (DIG):** every declared model directory has
   `workflow/`, `extractor/`, and `geneset.model.json`; invoke existing
   `validate_output_dir()`/metadata schema validation on the extractor path;
   require matching `geneset.provenance.json` wherever final metadata exists;
   require `manifest.tsv` for a declared grouped output; recompute declared
   checksums/sizes with `--check-files`.
4. **Wrapper policy validation (dev):** verify the staged tree contains command
   records and logs where produced, contains no `.orig`, cache, `__pycache__`,
   editor swap, credentials, or absolute-path manifest entries, and report
   untracked extra files rather than silently include them.

The validator emits a human-readable summary and a machine-readable JSON
report.  It is read-only by default.  Staging/refresh/publish are distinct
commands so validation can be repeated safely.

## Compatibility strategy

- Retain every current DIG command, workflow, converter, output filename, and
  schema meaning.
- Retain all current library wrappers/configs and their direct invocation paths.
- Do not add submission files into a library until its owner elects to adopt.
- Reuse model IDs, partition IDs, model manifests, description templates,
  `workflow/` + `extractor/`, final sidecars, and existing shared refresh and
  S3-publisher wrappers.
- Treat grouped and single extractor outputs as first-class because GTEx has
  grouped examples; never assume a single `geneset.meta.json` at model-root.
- Use an independent `submission` CLI namespace in DIG, preventing accidental
  behavior changes to `validate` and allowing wheel-level tests.
- Preserve original artifacts.  Refresh behavior remains the current refresh
  tool's behavior (including `.orig` GMT handling); staging copies only the
  selected final tree and records exactly what was included.

## CI design

### DIG workflow extension

Extend the existing `tests.yml` additively with submission unit/CLI tests as
part of the current `pytest -q` run and add a wheel smoke check:

```bash
omics2geneset submission validate --help
```

Use tiny checked-in synthetic trees; no cloud, scheduler, R, or large assay
inputs.  Existing wheel installation and alias smoke tests remain unchanged.

### New dev workflow

Add `.github/workflows/submission-system-v1.yml` triggered on pull requests and
pushes affecting the new system, docs, or fixtures.  Jobs:

1. run `python3 -m unittest geneset-extractor-dev/tests/test_submission_system_v1.py`;
2. invoke scaffold in a temporary directory and assert its tree/header files;
3. build a synthetic staged tree and run the dev validator in dry-run mode;
4. install/use the sibling DIG checkout in editable mode (or set `PYTHONPATH`)
   and run `geneset-extractors submission validate --check-files` against it;
5. execute no workflow, qsub, Apptainer, AWS, or S3 command.

Pin Python to 3.11 to match DIG CI.  The workflow must not touch existing
library outputs or require their non-public inputs.

## Testing strategy

| Layer | Tests |
| --- | --- |
| DIG unit | schema acceptance/rejection, path traversal, duplicate records, checksum mismatch, single/grouped artifact checks, sidecar presence. |
| DIG CLI | success/failure exit codes, JSON report, no mutation, package-wheel availability. |
| Dev unit | TSV parsing, stable worklist ordering, command argument rendering, config-to-existing-model cross-check, archive file selection. |
| Dev scaffold | fresh destination succeeds; populated/nonempty destination fails; generated TSV headers and run templates are correct. |
| Integration fixture | a minimal synthetic `workflow/` + `extractor/` tree with valid DIG-produced-style metadata/provenance/model sidecar validates end-to-end. |
| Compatibility | read-only validation fixtures modeled after existing GTEx grouped output and one single-output convention; no regeneration or modification of reference outputs. |
| Negative | missing provenance/model sidecar, mismatched hash, model not in config, extra undeclared file, invalid description-template reference, symlink/path escape. |

## Rollout phases

1. **Contract and fixtures:** add the DIG schema/validator and dev manifest
   assembly/scaffold code with synthetic tests only.
2. **CI:** enable the new additive workflows and wheel smoke test.
3. **Read-only pilot:** create a configuration for one explicitly selected
   existing library, run `validate` against a copied/staged known-good output,
   and compare its selected file list with the existing publisher dry run.  No
   existing run command changes.
4. **Opt-in adoption:** add one library's submission configuration and thin
   wrapper alias only after pilot acceptance; preserve direct legacy commands.
5. **Remaining libraries:** repeat one library at a time, each with a separate
   compatibility test and release note.
6. **Operational enablement:** only after users approve the archive layout,
   invoke existing refresh/publish commands from the new orchestration command;
   start in `--dry_run` mode.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A generic system accidentally imposes one output shape | Explicit `single`/`grouped` modes and reuse of DIG's existing grouped validator. |
| Divergence between model config and output | Cross-check selected IDs against existing model lists/manifests and record commits/config paths in the archive manifest. |
| Wrapper starts absorbing biological logic | Restrict dev code to configuration, subprocess orchestration, staging, and policy; code review rejects analysis/mapping/GMT code there. |
| Refresh helper is currently library-aware | Keep it unchanged in v1; delegate through existing per-library launchers. Generalization is a separate, compatibility-tested proposal. |
| Manifest leaks local paths or credentials | Require relative archive paths, reject suspicious files, and rely on existing provenance mirror/refresh mechanics. |
| Checksumming large trees is expensive | Separate fast schema mode from `--check-files`; report progress deterministically. |
| Scheduler/cloud commands run in CI | CI permits only synthetic validation and dry-run command rendering. |
| Existing files change during staging | Stage into a new explicit directory, hash after copy, validate the staged tree, and never mutate source outputs. |

## Proposed implementation commits

1. `add dig submission manifest validator`
2. `add submission system v1 wrapper scaffold`
3. `add submission system v1 validation tests`
4. `add submission system v1 ci`
5. `document submission system v1`

The commits above are intentionally ordered so reusable DIG validation and its
tests land before the wrapper orchestration that depends on it.  Per-library
adoption commits are intentionally excluded until a library owner chooses an
opt-in pilot.
