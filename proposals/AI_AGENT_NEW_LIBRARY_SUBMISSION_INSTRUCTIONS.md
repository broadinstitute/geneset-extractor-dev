# AI Agent Instructions: Create a New Gene-Set Library Submission

## Purpose

Create a complete, reviewable new-library submission using the two repositories already present in the current working directory:

- `dig-gene-set-extractors`
- `geneset-extractor-dev`

Use `rk-submission-system-v1` as the baseline branch in both repositories.

The input data files are also available somewhere under the current working directory. Inspect the directory carefully and identify them without modifying the originals.

Your goal is to produce:

1. Any reusable source-processing, analysis, mapping, and gene-set generation code required in `dig-gene-set-extractors`.
2. A new-format wrapper/configuration submission in `geneset-extractor-dev` containing `submission.yaml`.
3. Tests, small safe fixtures, complete reproduction metadata, and local validation results.
4. Two reviewable branches and draft pull-request descriptions. Do not merge anything.

---

## Non-negotiable architecture

### `dig-gene-set-extractors` owns substantive work

Put all substantive logic in `dig-gene-set-extractors`, including:

- source-data parsing and preprocessing;
- normalization;
- statistical analysis and differential testing;
- ranking and filtering;
- gene identifier mapping;
- gene-set construction;
- reusable workflows and converters;
- assay-specific metadata and provenance generation.

Prefer reusing an existing DIG workflow or converter whenever scientifically appropriate. Do not create a source-specific implementation when a small reusable extension to an existing workflow is sufficient.

### `geneset-extractor-dev` remains wrapper-only

The new library directory in `geneset-extractor-dev` may contain only:

- `submission.yaml`;
- source, model, partition, description, and output manifests;
- thin command construction and dispatch;
- reproduction entry points;
- runtime or cluster orchestration;
- metadata refresh and publishing integration.

Do not place normalization, differential analysis, gene mapping, ranking, gene-set construction, or custom GMT writing in `geneset-extractor-dev`.

### Complete-code requirement

The submission must include every piece of code needed to transform the declared source inputs into the final gene sets.

Do not depend on:

- private scripts outside the repositories;
- undocumented manual spreadsheet edits;
- unexplained precomputed intermediate files;
- contributor-specific absolute paths;
- uncommitted notebooks or local helper modules.

Large or controlled source files do not need to be committed, but every required input must be declared with source, release, access method, and redistribution status.

---

## Safety and data-handling rules

1. Never modify the original source data in place.
2. Never commit large source datasets, controlled-access data, credentials, tokens, signed URLs, private identifiers, or generated production outputs.
3. Inspect filenames, headers, shapes, types, and small samples only. Avoid printing sensitive rows unnecessarily.
4. Create smoke fixtures only from synthetic data or data explicitly safe to redistribute.
5. Use working directories outside Git for full source data and production outputs.
6. Do not run arbitrary remote scripts.
7. Do not push branches or open pull requests until the human approves the implementation and scientific plan.
8. Do not change branch protection, repository settings, existing library behavior, existing DIG CLI names, or existing output contracts.

---

## Phase 1: Repository and environment preflight

From the current working directory, locate both repositories and the likely input files.

Verify the branches:

```bash
git -C dig-gene-set-extractors branch --show-current
git -C geneset-extractor-dev branch --show-current
```

Both baselines must be `rk-submission-system-v1`. If either repository is on another branch, stop and report it rather than switching silently when uncommitted work exists.

Inspect repository state:

```bash
git -C dig-gene-set-extractors status --short
git -C geneset-extractor-dev status --short
```

Do not overwrite unrelated uncommitted work.

Inspect at minimum:

```text
dig-gene-set-extractors/
  README.md
  pyproject.toml
  src/geneset_extractors/
  tests/
  docs/assays/
  docs/submissions/

geneset-extractor-dev/
  docs/submissions/
  submission_tools/
  config/submission_system_v1.schema.json
  examples/synthetic_submission/
  tests/test_submission_tools.py
  run/test_submission_tools.sh
```

### Required portability check

Inspect `geneset-extractor-dev/tests/test_submission_tools.py` for a hard-coded interpreter path such as:

```text
/home/ryank/software/miniconda3/envs/work/bin/python
```

If present, do not treat that path as valid on the contributor's machine. Report it as a submission-system portability defect. For local testing, use the active Python interpreter. Do not include an unrelated infrastructure fix in the new-library submission branch unless the human explicitly approves it.

### Install DIG in an isolated environment

Use an environment local to `dig-gene-set-extractors`:

```bash
cd dig-gene-set-extractors
python3 -m venv .venv-submission
source .venv-submission/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
pytest -q tests/test_submission_contract.py
geneset-extractors submission list
```

Record all pre-existing test failures before changing code.

---

## Phase 2: Inspect and characterize the input data

Find likely source files under the current working directory, excluding repository internals, Git metadata, virtual environments, caches, and generated output directories.

For each candidate input, record:

- relative or external location;
- format and compression;
- approximate size;
- headers or schema;
- number of rows and columns when inexpensive to determine;
- identifier types;
- organism and genome build when inferable;
- sample metadata fields;
- whether it appears raw, normalized, summarized, differential, or already ranked;
- source name, stable URL/accession, release/version, license, and access restrictions if available from nearby documentation.

Do not assume scientific meaning solely from column names. Distinguish facts from inferences.

Determine what one final gene set should represent. Examples include:

- tissue × case-control contrast × direction;
- cell type × disease × direction;
- compound × dose × cell line;
- perturbation × model system;
- assay partition × phenotype;
- another source-specific model.

---

## Phase 3: Produce a scientific and implementation plan before editing

Create a proposed plan and show it to the human before implementing substantive code.

The plan must include:

1. **Inputs inspected** — files, formats, identifiers, and source metadata.
2. **Proposed biological interpretation** — what each gene set represents.
3. **Models and partitions** — how model IDs and partitions will be defined.
4. **Closest existing wrapper pattern** — one of:
   - `gtex`
   - `motrpac`
   - `hubmap`
   - `lincs_l1000`
   - `generic`
5. **Closest existing DIG workflow/converter** — determine by running:

   ```bash
   geneset-extractors submission list
   geneset-extractors submission describe <candidate_identifier>
   geneset-extractors submission validate <candidate_identifier>
   ```

6. **Reuse decision** — whether the submission can:
   - use an existing DIG identifier unchanged;
   - add reusable source preparation feeding an existing converter;
   - extend an existing converter;
   - require a new converter/workflow.
7. **Statistical choices** — contrasts, covariates, thresholds, directions, filtering, and mapping policy.
8. **Scientific assumptions requiring human approval**.
9. **Code locations** in both repositories.
10. **Test strategy** using synthetic or safely redistributable fixtures.
11. **Reproduction boundary** — original declared inputs through final gene sets.
12. **Files that must not be committed**.

Write the approved plan to:

```text
<NEW_LIBRARY_DIRECTORY>/AI_SUBMISSION_PLAN.md
```

Do not begin implementation until the human approves the biological interpretation and material statistical assumptions.

---

## Phase 4: Create contribution branches

After approval, create dedicated branches from the current `rk-submission-system-v1` baselines.

Use clear names, for example:

```bash
LIBRARY_ID='<safe_library_id>'

git -C dig-gene-set-extractors switch -c "${LIBRARY_ID}-dig"
git -C geneset-extractor-dev switch -c "${LIBRARY_ID}-wrapper"
```

The library ID must start with a letter and contain only letters, digits, `_`, or `-`.

Do not commit yet.

---

## Phase 5: Implement or reuse DIG functionality

Work in `dig-gene-set-extractors` first when new reusable processing is required.

### Prefer existing interfaces

Use the existing registry and CLI. Inspect related implementations and assay guides. Do not invent a parallel workflow framework.

The standard final files are:

```text
geneset.tsv
geneset.meta.json
geneset.provenance.json
```

### When new DIG code is needed

Add:

- source parsing or preparation code;
- reusable analytical logic;
- workflow/converter registration through existing mechanisms;
- unit tests;
- a tiny fixture;
- focused documentation.

Tests must cover, as applicable:

- required columns and malformed inputs;
- parsing and identifier handling;
- model/contrast construction;
- deterministic output;
- expected output files;
- metadata and provenance;
- CLI registration;
- useful failure messages.

Run:

```bash
cd dig-gene-set-extractors
source .venv-submission/bin/activate
pytest -q
pytest -q tests/test_submission_contract.py
geneset-extractors submission list
geneset-extractors submission describe <IDENTIFIER>
geneset-extractors submission validate <IDENTIFIER>
```

If an existing DIG identifier already handles the source correctly, do not add artificial DIG changes merely to create a paired PR. Record that no DIG code change is required and later use `N/A` for the DIG PR field while still pinning the exact tested DIG commit.

---

## Phase 6: Scaffold the wrapper submission

From `geneset-extractor-dev`, create the new library package with the approved pattern:

```bash
cd geneset-extractor-dev
python3 -m submission_tools scaffold \
  --library-id '<LIBRARY_ID>' \
  --display-name '<DISPLAY_NAME>' \
  --pattern '<gtex|motrpac|hubmap|lincs_l1000|generic>' \
  --output '<LIBRARY_ID>'
```

The output directory must not already exist.

The scaffold creates starter files including:

```text
<LIBRARY_ID>/
  submission.yaml
  README.md
  config/model_list.tsv
  config/partition_list.tsv
  config/model_description_templates.tsv
  reproduction/input_manifest.tsv
  reproduction/download_inputs.sh
  reproduction/reproduce.sh
  expected/output_manifest.tsv
  run/submit_models.sh
  src/README.md
  tests/fixtures/README.md
```

Keep `submission_status` as `draft` while implementing.

---

## Phase 7: Populate the wrapper package

### `submission.yaml`

Fill every relevant `TODO` with verified information. Required concepts include:

- schema version;
- draft/ready status;
- library ID and display name;
- organism and optional genome build;
- assay types;
- closest pattern;
- source name, stable URI/accession, release, access restrictions, and license;
- DIG repository URL;
- DIG entrypoints and identifiers;
- config paths;
- reproduction entry point and smoke command;
- expected-output manifest;
- environment declaration;
- deviations and allowlisted findings;
- paired PR references.

During development, use:

```json
"submission_status": "draft"
```

and:

```json
"commit": "TODO"
```

A ready submission requires a lowercase full 40-character DIG commit SHA.

### `reproduction/input_manifest.tsv`

Use the exact scaffold headers:

```text
input_id
source_uri_or_access_instructions
version_release
checksum
access_method
smoke_full
workflow_stage
redistribution_status
committed_fixture
fixture_path
```

Declare every external input and every committed smoke fixture.

Generate SHA-256 checksums automatically when feasible. Do not fabricate checksums. Controlled-access files may omit them only when infeasible; access instructions must remain explicit.

Every source in `submission.yaml` must correspond to an input manifest record.

### Model, partition, and description tables

Populate:

```text
config/model_list.tsv
config/partition_list.tsv
config/model_description_templates.tsv
```

Requirements:

- unique, stable model IDs;
- explicit enabled/disabled state;
- partitions that match the source organization;
- descriptions that state biological meaning, contrast, direction, partition, and source where relevant;
- no hidden model construction in opaque shell conditionals.

Use the scaffold's exact headers unless the validator and wrapper are intentionally extended together.

### Thin wrapper and execution scripts

Implement only command construction and dispatch in the wrapper repository.

`reproduction/reproduce.sh` must:

- be executable;
- use `set -euo pipefail`;
- support `--smoke`;
- invoke committed DIG code;
- avoid undocumented intermediates and private helpers.

`reproduction/download_inputs.sh` may download public files and verify checksums, or print precise controlled-access placement instructions. Never embed credentials.

### Smoke fixtures

Place only small synthetic or explicitly redistributable fixtures under:

```text
<LIBRARY_ID>/tests/fixtures/
```

Declare each fixture in `input_manifest.tsv` with `committed_fixture=true` and the correct `fixture_path`.

### Expected outputs

Populate `expected/output_manifest.tsv` using the exact headers:

```text
output_id
relative_path
role
required
model_id
partition_id
```

List the expected review contract; do not commit large production outputs merely to satisfy it.

---

## Phase 8: Validate during development

Run static wrapper validation:

```bash
cd geneset-extractor-dev
python3 -m submission_tools validate \
  --submission '<LIBRARY_ID>/submission.yaml'
```

Run coordinated validation against the sibling DIG checkout:

```bash
python3 -m submission_tools validate \
  --submission '<LIBRARY_ID>/submission.yaml' \
  --dig-repo ../dig-gene-set-extractors \
  --development-dig-checkout \
  --smoke
```

The development override must be explicit and may be used only while the DIG checkout is intentionally dirty or not yet pinned.

Run the wrapper test suite:

```bash
bash run/test_submission_tools.sh
```

If that script fails solely because the branch still contains a contributor-specific hard-coded Python interpreter path, report the portability defect separately. Do not conceal it or claim all tests passed.

Run the reproduction smoke command directly as well:

```bash
cd '<LIBRARY_ID>'
bash reproduction/reproduce.sh --smoke
```

A successful static validation alone does not prove that the biological pipeline runs.

---

## Phase 9: Test with a representative subset and full data

Use working directories outside Git.

Run the actual DIG path on:

1. a small representative subset of the real source data;
2. the full source data when practical and authorized.

Verify:

- every enabled model completes;
- expected outputs exist;
- identifiers and directions are correct;
- metadata records source release and parameters;
- provenance references meaningful declared inputs;
- no sensitive sample identifiers appear in public names;
- rerunning is reproducible within the method's expected behavior;
- no manual edits are required between stages.

Do not commit source data or full generated outputs.

Record the exact commands and results in `AI_SUBMISSION_PLAN.md` or a separate `VALIDATION_REPORT.md` under the new library directory.

---

## Phase 10: Pin DIG and mark the wrapper ready

Ensure the DIG working tree is clean and commit the DIG implementation when applicable.

Record the exact commit:

```bash
git -C dig-gene-set-extractors rev-parse HEAD
```

Update `submission.yaml`:

- set `dig.commit` to the full lowercase 40-character SHA;
- set concrete DIG identifiers;
- change `submission_status` from `draft` to `ready` only after all required fields and tests are complete.

Run final coordinated validation without the development override:

```bash
cd geneset-extractor-dev
python3 -m submission_tools validate \
  --submission '<LIBRARY_ID>/submission.yaml' \
  --dig-repo ../dig-gene-set-extractors \
  --smoke \
  --receipt-out '<LIBRARY_ID>/run_receipt.json'
```

The DIG checkout must be clean and its `HEAD` must match the declared SHA.

Also run:

```bash
bash run/test_submission_tools.sh
```

Do not claim success if any required test fails.

---

## Phase 11: Review the complete diff

Before committing, inspect:

```bash
git -C dig-gene-set-extractors status
git -C dig-gene-set-extractors diff --stat
git -C dig-gene-set-extractors diff

git -C geneset-extractor-dev status
git -C geneset-extractor-dev diff --stat
git -C geneset-extractor-dev diff
```

Check for accidental large or sensitive files:

```bash
find geneset-extractor-dev/'<LIBRARY_ID>' -type f -size +10M -print
```

Search for suspicious local paths and secrets, reviewing each match rather than deleting legitimate public URIs blindly.

Confirm existing legacy libraries were not modified unless the change is an approved documentation-only link.

---

## Phase 12: Prepare commits and draft PR material

Only after human approval, create separate commits in each repository.

Suggested commit messages:

```text
DIG: Add extractor support for <LIBRARY_ID>
Wrapper: Add <LIBRARY_ID> gene-set library submission
```

Prepare two draft pull-request descriptions.

### DIG PR

Target:

```text
base: rk-submission-system-v1
```

Include:

- source and data type;
- biological meaning of each set;
- reused/new DIG identifiers;
- transformation stages;
- fixtures and tests;
- focused and full test results;
- representative/full-data run summary;
- known limitations.

### Wrapper PR

Target:

```text
base: rk-submission-system-v1
```

Include:

- library path and `submission.yaml` path;
- DIG PR or `N/A`;
- exact DIG SHA;
- source/input manifest summary;
- full reproduction command;
- smoke command;
- confirmation that all transformation code is included;
- confirmation that no manual transformations are required;
- confirmation that substantive logic is in DIG;
- static, coordinated, smoke, and full-data validation results;
- declared deviations and unresolved issues.

When PR URLs exist, update `paired_pull_requests` in `submission.yaml`, revalidate, and commit that metadata update.

Do not merge either PR.

---

## Final report to the human

At completion, provide a concise report containing:

1. Library ID and display name.
2. Input files inspected and source metadata.
3. Biological interpretation and approved scientific decisions.
4. DIG identifier(s) reused or added.
5. Files created or modified in each repository.
6. Exact commands executed.
7. Test results, separated into:
   - pre-existing results;
   - DIG tests;
   - wrapper static validation;
   - coordinated validation;
   - direct smoke reproduction;
   - representative real-data run;
   - full-data run.
8. Any failures or limitations, including infrastructure portability defects.
9. DIG commit SHA pinned in `submission.yaml`.
10. Proposed branch names and draft PR descriptions.
11. Files intentionally excluded from Git.
12. Remaining human review items.

Never state that a check passed unless you ran it and observed a successful exit status.
