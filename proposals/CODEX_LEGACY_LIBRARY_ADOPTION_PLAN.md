# Legacy Gene-Set Library Adoption for `rk-submission-system-v1`

## Purpose

Extend the current `rk-submission-system-v1` submission system so that users who have **already generated gene sets outside the new submission framework** can migrate their existing implementation into the new standard.

The goal is **not** to create a weaker "legacy" standard. The adoption path should help users convert an existing workflow into the same reproducibility, architecture, and validation contract required for new submissions.

A legacy submission may contain:

- Python, R, shell, notebook, Snakemake, Nextflow, or Make-based code
- source/input data
- manually generated intermediate files
- already-generated GMT or other gene-set outputs
- custom directory layouts
- local or cluster-specific paths
- environment files
- incomplete provenance
- undocumented manual steps

The adoption system should inventory these materials, identify compliance gaps, scaffold a normal new-format submission, generate a migration plan for an AI coding agent, and then reuse the existing deterministic validation and CI machinery.

---

# Core Design Principle

The adoption path should work as follows:

```text
existing legacy library
        ↓
submission_tools adopt
        ↓
deterministic inventory + compliance analysis
        ↓
AI-assisted migration
        ↓
normal rk-submission-system-v1 validation
        ↓
legacy-vs-new output comparison
        ↓
normal CI + review
```

The AI agent may perform most of the code migration, but **the AI must not be the authority that determines whether its own migration is valid**.

Validation remains deterministic:

```text
AI agent
    generates/adapts implementation
        ↓
submission validator
    checks repository contract
        ↓
CI
    repeats checks in a clean environment
        ↓
human reviewer
    reviews scientific correctness
```

---

# Architectural Requirements

The existing repository boundary remains unchanged.

## `dig-gene-set-extractors`

All substantive processing belongs here, including:

- source-data parsing
- preprocessing
- normalization
- statistical analysis
- differential testing
- ranking
- gene identifier mapping
- gene-set construction
- reusable converters
- workflow implementations

## `geneset-extractor-dev`

This repository remains wrapper/submission/orchestration only:

- `submission.yaml`
- input/output manifests
- model configuration
- partition configuration
- thin DIG command construction
- reproduction entry points
- migration/adoption metadata
- AI migration prompt generation
- old/new output comparison
- publishing integration

Do **not** introduce a permanent exception that allows legacy submissions to keep substantive analysis code in `geneset-extractor-dev`.

---

# User-Facing Command

Add a first-class legacy adoption command:

```bash
python3 -m submission_tools adopt \
    --existing PATH_TO_EXISTING_LIBRARY \
    --library-id LIBRARY_ID \
    --dig-repo ../dig-gene-set-extractors
```

A minimal form should also work:

```bash
python3 -m submission_tools adopt \
    --existing PATH_TO_EXISTING_LIBRARY \
    --library-id LIBRARY_ID
```

The command should **not modify the original legacy directory**.

It should create a normal new-format library scaffold plus an `adoption/` directory.

Example:

```text
LIBRARY_ID/
├── submission.yaml
├── config/
├── reproduction/
├── expected/
├── src/
├── tests/
└── adoption/
    ├── inventory.json
    ├── adoption_report.md
    └── AI_ADOPTION_PROMPT.md
```

---

# What `adopt` Should Do

## 1. Inventory the legacy directory

Recursively inspect the existing submission.

Recognize common code files:

```text
*.py
*.R
*.r
*.sh
*.ipynb
Snakefile
*.smk
*.nf
nextflow.config
Makefile
```

Record:

- relative path
- file size
- checksum
- language/type
- likely role
- apparent entrypoint where inferable

Recognize common data files:

```text
*.tsv
*.tsv.gz
*.csv
*.csv.gz
*.gct
*.gct.gz
*.h5
*.h5ad
*.rds
*.RData
*.parquet
```

Record:

- relative path
- file size
- checksum
- header/column names where inexpensive and safe
- likely classification:
  - source input
  - intermediate
  - output
  - unknown

Do not read entire large files into memory merely for inventory.

Recognize gene-set outputs:

```text
*.gmt
geneset.tsv
*.geneset.tsv
*.json
```

For GMT-like outputs, record:

- file path
- number of gene sets
- set names where feasible
- approximate set-size distribution
- checksum

Recognize environment files:

```text
environment.yml
environment.yaml
requirements.txt
requirements-dev.txt
pyproject.toml
poetry.lock
uv.lock
renv.lock
Dockerfile
*.def
```

---

# Nonportable and Risky Pattern Detection

Scan text/code files for suspicious assumptions such as:

```text
/home/
/Users/
/humgen/
/broad/
scratch paths
hard-coded personal directories
credentials
tokens
passwords
manual copy commands from private directories
```

Do not automatically reject the inventory stage.

Flag findings in the adoption report.

Also scan documentation/comments/scripts for likely manual steps such as:

```text
manually
open in Excel
edit this file
copy this file
download by hand
rename manually
filter rows
paste
```

These should be surfaced as reproducibility risks.

---

# Inventory Output

Create:

```text
adoption/inventory.json
```

Use a versioned structure.

Example conceptual shape:

```json
{
  "schema_version": "1.0.0",
  "legacy_root": "../legacy_library",
  "code_files": [],
  "data_files": [],
  "gene_set_outputs": [],
  "environment_files": [],
  "nonportable_findings": [],
  "manual_step_findings": [],
  "possible_intermediates": []
}
```

Do not store secrets or raw large-file contents.

Prefer relative paths and checksums.

---

# Adoption Report

Generate:

```text
adoption/adoption_report.md
```

The report should summarize findings in human-readable form.

Example:

```text
LEGACY ADOPTION AUDIT

Source inputs
  ✓ counts.tsv.gz
  ✓ metadata.tsv
  ? gene_annotation.tsv — unclear whether source or generated

Processing code
  ✓ preprocess.py
  ✓ analysis.R
  ✓ make_gmt.py

Reproducibility gaps
  ✗ differential_results.tsv has no apparent producer
  ✗ analysis.R contains /humgen/users/alice/data
  ✗ no environment lock
  ✗ no provenance generation

Architecture gaps
  ✗ differential analysis currently lives outside DIG
  ✗ GMT generation currently lives outside DIG

Reusable DIG components
  ✓ rna_deg_multi appears potentially compatible

Existing output
  ✓ legacy_genesets.gmt: 216 gene sets

Adoption readiness: REQUIRES MIGRATION
```

The report should distinguish:

- informational findings
- warnings
- blockers

---

# Scaffold a Normal New-Format Submission

The `adopt` command should reuse the existing scaffold code rather than build a separate legacy format.

Create the standard submission files:

```text
submission.yaml
config/
reproduction/
expected/
src/
tests/
```

Do not weaken their validation requirements.

Add an optional section to `submission.yaml`:

```yaml
submission_origin:
  type: adopted
  legacy_inventory: adoption/inventory.json
```

For normal new submissions:

```yaml
submission_origin:
  type: new
```

This field is informational and should not change final validation standards.

---

# Generate an AI Migration Prompt

Create:

```text
adoption/AI_ADOPTION_PROMPT.md
```

This should be generated from the actual inventory and adoption report rather than being completely generic.

The generated prompt should instruct the AI coding agent to:

1. Inspect both sibling repositories.
2. Use `rk-submission-system-v1` as the baseline.
3. Inspect the legacy code and inventory.
4. Reconstruct the complete dependency chain from source inputs to final gene sets.
5. Identify every intermediate file.
6. Determine which committed code creates each intermediate.
7. Refuse to treat unexplained precomputed intermediates as acceptable final dependencies.
8. Reuse existing DIG workflows/converters wherever scientifically equivalent.
9. Move or reimplement substantive processing in `dig-gene-set-extractors`.
10. Keep `geneset-extractor-dev` wrapper-only.
11. Generate all required submission/config/reproduction files.
12. Add small smoke fixtures.
13. Add DIG tests.
14. Preserve the intended scientific meaning.
15. Compare regenerated outputs to existing gene sets.
16. Classify every difference.
17. Do not silently alter scientific parameters.
18. Run the standard coordinated validation at the end.
19. Do not modify the original legacy directory.

A generated prompt should include paths to:

```text
legacy implementation
adoption/inventory.json
adoption/adoption_report.md
reference legacy gene-set outputs
both sibling repositories
```

---

# Required AI Migration Rule

The generated prompt must contain language equivalent to:

> Having previously generated gene sets is not sufficient. Every required intermediate must either be a declared source input or be generated by committed code in the migrated workflow.

And:

> All substantive source-data processing, statistical analysis, gene mapping, ranking, and gene-set generation must live in `dig-gene-set-extractors`.

And:

> `geneset-extractor-dev` may contain only configuration, thin orchestration, reproduction metadata, adoption metadata, and publishing integration.

---

# Dependency Reconstruction

The migration process should explicitly reconstruct a dependency graph.

Example legacy flow:

```text
counts.tsv
metadata.tsv
    ↓
prepare.py
    ↓
filtered_counts.tsv
    ↓
analysis.R
    ↓
de.tsv
    ↓
make_sets.py
    ↓
genesets.gmt
```

Target architecture:

```text
declared source inputs
        ↓
DIG preparation workflow
        ↓
DIG analysis/converter
        ↓
standard DIG output
        ↓
thin geneset-extractor-dev wrapper
```

If a required intermediate such as:

```text
de.tsv
```

exists but no producer can be identified, adoption must remain incomplete until the transformation code is supplied or reconstructed.

---

# Legacy Output as a Regression Target

Existing gene sets are valuable and should be used as a reference during migration.

Support an optional adoption configuration such as:

```yaml
adoption:
  reference_outputs:
    - path: adoption/reference/old_genesets.gmt
      comparison: set_equivalent
```

Do not require copying very large legacy outputs into Git if they are unsuitable for version control.

Allow references by external path or checksum where appropriate during local adoption.

---

# Comparison Modes

Implement legacy-vs-new comparison modes.

## `exact`

Use when byte-level or fully deterministic equivalence is expected.

Check:

- same gene-set names
- same membership
- same ordering where applicable
- same values/weights where applicable

## `set_equivalent`

Use when ordering is irrelevant.

Check:

- same gene-set names
- same gene membership
- ignore member ordering

## `report_only`

Use when the migrated workflow intentionally changes old behavior.

Produce a comparison report but do not fail solely because differences exist.

---

# New Command: `compare-legacy`

Add:

```bash
python3 -m submission_tools compare-legacy \
    --library LIBRARY_ID
```

Allow optional explicit paths:

```bash
python3 -m submission_tools compare-legacy \
    --legacy OLD_FILE.gmt \
    --new NEW_FILE.gmt \
    --mode set_equivalent
```

Generate:

```text
adoption/comparison_report.tsv
adoption/comparison_summary.md
```

The summary should report, for example:

```text
216 total legacy gene sets
212 unchanged
2 membership differences
1 missing
1 newly generated
```

Where possible, report:

- missing sets
- new sets
- membership differences
- number of genes added
- number of genes removed
- ordering-only differences

Do not silently normalize scientifically meaningful differences away.

---

# Adoption Status Model

Add progressive migration states.

Suggested states:

```text
INVENTORIED
DEPENDENCIES_RESOLVED
ARCHITECTURE_MIGRATED
NEW_FORMAT_VALID
SMOKE_REPRODUCIBLE
LEGACY_COMPARED
READY
```

Definitions:

## `INVENTORIED`

Legacy files have been catalogued.

## `DEPENDENCIES_RESOLVED`

Every required input/intermediate has a known source or producer.

## `ARCHITECTURE_MIGRATED`

All substantive processing now resides in DIG.

## `NEW_FORMAT_VALID`

Normal `submission.yaml` and manifest validation passes.

## `SMOKE_REPRODUCIBLE`

The migrated smoke test succeeds.

## `LEGACY_COMPARED`

New outputs have been compared against the legacy reference.

## `READY`

All standard submission requirements are satisfied.

---

# New Command: `adoption-status`

Add:

```bash
python3 -m submission_tools adoption-status \
    --library LIBRARY_ID
```

Example output:

```text
✓ INVENTORIED
✓ DEPENDENCIES_RESOLVED
✓ ARCHITECTURE_MIGRATED
✓ NEW_FORMAT_VALID
✓ SMOKE_REPRODUCIBLE
! LEGACY_COMPARED
  4 of 216 sets differ
✗ READY
```

This should be informational and easy for contributors to understand.

---

# No Permanent Legacy Bypass

Do **not** add a general bypass such as:

```text
--allow-legacy
```

that permits weaker submissions.

The intended model is:

```text
legacy implementation
        ↓
migration assistance
        ↓
same final contract as a new submission
```

The adoption workflow may be permissive while inventorying, but `READY` status must satisfy the normal submission system.

---

# Suggested Code Additions

Primarily in `geneset-extractor-dev`:

```text
submission_tools/
├── adoption.py
├── inventory.py
├── legacy_compare.py
├── adoption_status.py
└── templates/
    └── ai_adoption_prompt.md
```

Integrate with the current `submission_tools` CLI rather than introducing a separate executable.

Potential CLI commands:

```bash
python3 -m submission_tools adopt ...
python3 -m submission_tools adoption-status ...
python3 -m submission_tools compare-legacy ...
```

Reuse existing modules for:

- scaffold generation
- schema validation
- wrapper-boundary validation
- coordinated DIG validation
- smoke validation
- receipts

Avoid duplicating validation logic.

---

# DIG-Side Changes

Do not add general adoption orchestration to `dig-gene-set-extractors`.

DIG should only receive changes that the migrated library itself requires:

- new reusable preprocessing code
- new workflow
- new converter
- new CLI registration
- tests
- fixtures
- documentation

The migration/inventory/comparison system belongs in `geneset-extractor-dev`.

---

# Minimal Version 1

Do not build every possible feature at once.

The first implementation should include:

## Command

```bash
python3 -m submission_tools adopt \
    --existing PATH \
    --library-id ID
```

## Behavior

1. Inventory the legacy directory.
2. Detect code, data, gene-set outputs, environment files, nonportable paths, and likely manual steps.
3. Reuse the normal scaffold to create a new-format submission.
4. Create:

```text
adoption/inventory.json
adoption/adoption_report.md
adoption/AI_ADOPTION_PROMPT.md
```

5. Identify existing gene-set output files as possible regression targets.
6. Tell the contributor to give `AI_ADOPTION_PROMPT.md` to their coding agent.
7. After AI migration, use the existing command:

```bash
python3 -m submission_tools validate \
    --submission LIBRARY_ID/submission.yaml \
    --dig-repo ../dig-gene-set-extractors \
    --smoke
```

## Also implement

```bash
python3 -m submission_tools compare-legacy \
    --library LIBRARY_ID
```

with at least:

- `exact`
- `set_equivalent`
- `report_only`

comparison modes.

This minimal implementation provides most of the value without redesigning the current submission system.

---

# Expected User Workflow

The final user experience should be approximately:

```bash
# 1. Inventory and scaffold the legacy implementation
python3 -m submission_tools adopt \
    --existing ../my_existing_library \
    --library-id my_library \
    --dig-repo ../dig-gene-set-extractors

# 2. Give the generated prompt to the user's coding agent
my_library/adoption/AI_ADOPTION_PROMPT.md

# 3. After the agent migrates the code
python3 -m submission_tools validate \
    --submission my_library/submission.yaml \
    --dig-repo ../dig-gene-set-extractors \
    --smoke

# 4. Compare regenerated gene sets to the old result
python3 -m submission_tools compare-legacy \
    --library my_library

# 5. Inspect migration status
python3 -m submission_tools adoption-status \
    --library my_library
```

After reaching `READY`, submission proceeds through the normal paired-PR and CI process.

---

# Testing Requirements

Add tests covering at least:

## Inventory

- Python/R/shell/notebook detection
- common data-file detection
- GMT detection
- environment-file detection
- checksums
- large-file-safe inspection
- nonportable path detection
- manual-step keyword detection

## Adoption

- legacy directory is not modified
- scaffold is created
- `submission_origin.type == adopted`
- inventory is written
- report is written
- AI prompt is generated
- existing gene-set outputs are identified

## Dependency gaps

- an unexplained intermediate is flagged
- a known producer resolves the intermediate
- declared source inputs are not incorrectly treated as unexplained intermediates

## Legacy comparison

- exact match
- ordering-only difference
- set-equivalent match
- added gene
- removed gene
- missing gene set
- additional gene set
- report-only mode

## Status

- each adoption state
- READY only after standard validation requirements pass
- legacy status never bypasses normal ready validation

## Compatibility

- existing new-format submissions still work unchanged
- legacy libraries without adoption metadata are unaffected
- current CI behavior remains unchanged unless adoption files are part of the submission
- no existing GTEx/MoTrPAC/HuBMAP/LINCS behavior is modified

---

# Documentation

Add:

```text
docs/submissions/adopting-existing-library.md
```

Keep it short and user-facing.

It should explain:

1. Use this path if gene sets were already produced outside the new submission framework.
2. Run `submission_tools adopt`.
3. Give the generated AI prompt to a coding agent.
4. Review scientific assumptions and any missing dependencies.
5. Run standard validation.
6. Compare regenerated outputs to the old outputs.
7. Proceed with the normal submission workflow when `READY`.

Also link this page from:

```text
docs/submissions/README.md
```

---

# Critical Acceptance Criteria

Do not consider this feature complete unless all of the following are true:

- Original legacy directories are never modified.
- Legacy code can be inventoried without requiring it to already follow repository conventions.
- Existing final gene sets can be preserved as migration/regression references.
- Unexplained intermediates are surfaced.
- The generated AI prompt clearly enforces the DIG/wrapper architectural boundary.
- The migration path produces a standard new-format submission.
- No permanent legacy-validation bypass exists.
- Final READY status requires the same normal submission validation used for new libraries.
- Old/new gene-set comparison is supported.
- Existing `rk-submission-system-v1` behavior remains backward-compatible.
