# Codex Implementation Brief: Isolated Legacy Adoption + Verification + PR Submission

## Scope

Update `rk-submission-system-v1` so that adopting an existing legacy gene-set submission is simple, safe, isolated, and highly automated.

The desired user-facing workflow is:

```text
adopt
  ↓
AI agent migration
  ↓
verify-adoption
  ↓
submit-adoption
```

The contributor should not need to manually manage temporary branches, DIG commit pinning, paired PR metadata, or most validation subcommands.

The adoption workflow must operate in a **completely isolated workspace** supplied by the user and must not modify:

- the user's existing local DIG checkout;
- the user's existing local `geneset-extractor-dev` checkout;
- the original legacy submission;
- the official upstream GitHub repositories.

Use contributor forks as the default writable Git remotes.

---

# Core Safety Model

The workflow should use:

```text
contributor fork = writable origin
official repository = read-only upstream
```

For DIG:

```text
origin   -> USERNAME/dig-gene-set-extractors
upstream -> flannick/dig-gene-set-extractors
```

For wrapper:

```text
origin   -> USERNAME/geneset-extractor-dev
upstream -> broadinstitute/geneset-extractor-dev
```

The tool must never push to `upstream`.

Forks should be strongly recommended and treated as the normal workflow.

An advanced override may exist for maintainers, but it must be explicit, e.g.:

```text
--allow-upstream-origin
```

Do not silently permit writable upstream origins.

---

# Command 1: `adopt`

Add or extend the command so the normal form is:

```bash
python3 -m submission_tools adopt \
    --existing /path/to/legacy_submission \
    --library-id my_library \
    --workspace ~/gene-set-adoptions/my_library \
    --github-user USERNAME
```

If `--github-user` is supplied, infer fork URLs as:

```text
https://github.com/USERNAME/dig-gene-set-extractors.git
https://github.com/USERNAME/geneset-extractor-dev.git
```

Also support explicit fork URLs for advanced users:

```bash
--dig-fork URL
--wrapper-fork URL
```

The tool already knows the canonical upstream repositories:

```text
https://github.com/flannick/dig-gene-set-extractors.git
https://github.com/broadinstitute/geneset-extractor-dev.git
```

The baseline branch for the current development system is:

```text
rk-submission-system-v1
```

Do not use `main` yet unless explicitly requested.

---

# Workspace Layout

`adopt` should create a dedicated workspace like:

```text
~/gene-set-adoptions/my_library/
├── .adoption-workspace.yaml
├── AI_ADOPTION_PROMPT.md
├── dig-gene-set-extractors/
├── geneset-extractor-dev/
├── adoption/
│   ├── inventory.json
│   ├── adoption_report.md
│   ├── dependency_map.json
│   └── legacy_reference.json
├── reports/
├── work/
└── legacy/
```

The exact layout can vary slightly if needed, but all generated work must remain inside the workspace except read-only references to the original legacy source.

---

# Workspace Safety Rules

Before creating anything, `adopt` must verify:

```text
workspace does not already contain unrelated files
workspace is not inside an existing DIG repo
workspace is not inside an existing wrapper repo
workspace is not inside the legacy submission
legacy submission is not inside the workspace
workspace is not the same path as any existing repository
```

If unsafe:

```text
ERROR: Adoption workspace must be a separate directory.

Example:
  --workspace ~/gene-set-adoptions/my_library
```

Do not attempt to continue.

---

# Fresh Clones Only

`adopt` should clone fresh copies of both contributor forks into the workspace.

Do not reuse arbitrary existing local checkouts.

Clone:

```text
USERNAME/dig-gene-set-extractors
USERNAME/geneset-extractor-dev
```

Then configure canonical upstream remotes.

Example expected remotes:

```text
origin    contributor fork
upstream  canonical repository
```

Fetch upstream and check out:

```text
rk-submission-system-v1
```

Then create dedicated working branches in both repositories:

```text
adopt/my_library
```

If a branch with that name already exists in the workspace clone, fail clearly or require an explicit resume mode.

---

# `.adoption-workspace.yaml`

Create a workspace manifest at:

```text
.adoption-workspace.yaml
```

Example conceptual schema:

```yaml
schema_version: 1

library_id: my_library

workspace:
  root: /absolute/path/to/workspace

legacy:
  source_path: /absolute/path/to/legacy_submission
  read_only: true
  inventory: adoption/inventory.json

repositories:
  dig:
    path: dig-gene-set-extractors
    origin: https://github.com/USERNAME/dig-gene-set-extractors.git
    upstream: https://github.com/flannick/dig-gene-set-extractors.git
    base_branch: rk-submission-system-v1
    work_branch: adopt/my_library

  wrapper:
    path: geneset-extractor-dev
    origin: https://github.com/USERNAME/geneset-extractor-dev.git
    upstream: https://github.com/broadinstitute/geneset-extractor-dev.git
    base_branch: rk-submission-system-v1
    work_branch: adopt/my_library

submission:
  wrapper_library_path: geneset-extractor-dev/my_library

verification:
  last_result: null
  last_receipt: null
```

This file should become the authoritative workspace configuration for `verify-adoption` and `submit-adoption`.

---

# Legacy Submission Protection

The original legacy submission must be treated as read-only.

Do not modify, rename, delete, or create files in it.

Options:

1. Store only its absolute path in `.adoption-workspace.yaml`; or
2. Create a read-only symlink:

```text
legacy/source -> /path/to/original
```

Do not recursively copy large legacy data by default.

Record file hashes in the adoption inventory.

At verification time, compare current hashes to the original inventory and fail if legacy files changed unexpectedly.

Example:

```text
FAILED: Legacy source changed during adoption.

Changed:
  scripts/run_analysis.R
```

---

# Adoption Inventory

Reuse the existing adoption inventory implementation.

Continue generating:

```text
adoption/inventory.json
adoption/adoption_report.md
adoption/dependency_map.json
```

Detect:

- code files;
- data files;
- GMT/gene-set outputs;
- environment files;
- possible intermediates;
- nonportable paths;
- manual-step indicators.

Do not read entire large data files unnecessarily.

---

# Legacy Reference Output

Identify likely legacy gene-set outputs.

If multiple GMT files are found, record all candidates and make the AI prompt ask the agent to identify the authoritative reference if it cannot be inferred.

Create:

```text
adoption/legacy_reference.json
```

Conceptual form:

```json
{
  "reference_outputs": [
    {
      "path": "/absolute/path/to/legacy/genesets.gmt",
      "checksum": "sha256:...",
      "comparison": "set_equivalent"
    }
  ]
}
```

Default comparison mode for a known-good legacy migration:

```text
set_equivalent
```

Do not copy large outputs into Git unless they are small and appropriate.

---

# Scaffold the New Submission Inside the Workspace

The normal scaffold must be created inside:

```text
geneset-extractor-dev/my_library/
```

Reuse existing scaffold code.

The resulting submission should still follow the standard `rk-submission-system-v1` contract.

Add adoption metadata such as:

```yaml
submission_origin:
  type: adopted
  legacy_inventory: ../../adoption/inventory.json
```

Use valid relative paths according to the existing schema design.

Do not create a separate legacy-only submission format.

---

# Generate Root `AI_ADOPTION_PROMPT.md`

Generate:

```text
WORKSPACE/AI_ADOPTION_PROMPT.md
```

This is the file the contributor gives to Codex, Claude Code, Copilot, or another coding agent.

The prompt must be workspace-aware and explicitly state:

```text
You are operating inside an isolated adoption workspace.

You may modify only:
- ./dig-gene-set-extractors
- ./geneset-extractor-dev
- generated adoption/report files inside this workspace

The original legacy submission is READ ONLY.

Do not modify files outside this workspace.
```

It must also enforce:

- substantive processing belongs in DIG;
- wrapper repo remains orchestration/config only;
- every intermediate must be either a declared source input or generated by committed code;
- preserve scientific behavior;
- do not silently change thresholds, mappings, contrasts, normalization, ranking, or model definitions;
- stop for approval before scientifically meaningful changes;
- add smoke fixtures and tests;
- run standard validation;
- regenerate gene sets;
- compare against the legacy reference.

Include the exact workspace paths and current branch names.

---

# End-of-`adopt` Output

After successful setup, print something concise:

```text
Adoption workspace ready:

  /home/user/gene-set-adoptions/my_library

Repositories:
  DIG:     contributor fork, branch adopt/my_library
  Wrapper: contributor fork, branch adopt/my_library

Legacy source:
  /path/to/legacy_submission
  READ ONLY

AI instructions:
  /home/user/gene-set-adoptions/my_library/AI_ADOPTION_PROMPT.md

Next:
  cd /home/user/gene-set-adoptions/my_library
  codex

Then tell your agent:
  Follow AI_ADOPTION_PROMPT.md.
```

Also explicitly print:

```text
No existing repositories or legacy files were modified.
```

---

# Command 2: `verify-adoption`

Add a high-level command:

```bash
python3 -m submission_tools verify-adoption \
    --workspace ~/gene-set-adoptions/my_library
```

This should infer everything from `.adoption-workspace.yaml`.

Do not require users to manually pass:

- DIG repo path;
- wrapper repo path;
- library ID;
- legacy GMT path;
- DIG SHA;
- development mode;
- receipt path;
- comparison mode.

Infer those automatically.

---

# `verify-adoption` Safety Checks

Before validation:

```text
✓ workspace manifest exists
✓ command is operating inside expected workspace
✓ DIG repo path matches workspace manifest
✓ wrapper repo path matches workspace manifest
✓ both repos are Git repositories
✓ both are on adopt/my_library
✓ origin points to contributor fork
✓ upstream points to canonical repo
✓ legacy source exists
✓ legacy source hashes match original inventory
```

If any safety check fails, stop.

---

# Automatic Development Mode

If DIG has uncommitted migration changes:

```text
DIG checkout contains uncommitted migration changes.
Running coordinated validation in development mode.
```

Automatically use the equivalent of:

```text
--development-dig-checkout
```

Do not require the contributor to know this option.

If DIG is clean:

```text
DIG checkout is clean.
Using exact commit validation.
```

If necessary, automatically update the draft submission's DIG commit during verification or report the mismatch with a clear fix.

Do not silently mark a submission `ready` while DIG is dirty.

---

# What `verify-adoption` Should Run

Orchestrate existing low-level functions rather than duplicating them.

Run:

1. Workspace safety checks.
2. Legacy integrity/hash checks.
3. Adoption inventory completeness checks.
4. Dependency resolution checks.
5. Wrapper-boundary validation.
6. DIG submission/interface validation.
7. DIG focused tests.
8. Wrapper submission-tool tests.
9. Standard submission schema validation.
10. Coordinated DIG validation.
11. Smoke reproduction.
12. Expected-output validation.
13. Metadata/provenance validation where supported.
14. Legacy-vs-new comparison.
15. Run-receipt generation.
16. Adoption status evaluation.

Do not automatically run extremely expensive full biological datasets unless explicitly configured.

The command should use the small smoke test for routine verification.

---

# Legacy Comparison During Verification

Default to:

```text
set_equivalent
```

unless the adoption metadata specifies another mode.

Report:

```text
legacy sets
new sets
unchanged
different
missing
new
genes added
genes removed
```

If the legacy output is expected to be preserved and membership differs, verification should fail unless the submission explicitly uses an approved `report_only` comparison mode.

Do not silently change the reference output.

---

# `verify-adoption` Output

Successful example:

```text
Adoption verification: PASS

✓ Workspace safety
✓ Legacy source unchanged
✓ Legacy inventory complete
✓ Dependencies resolved
✓ Wrapper-only architecture
✓ DIG submission interface
✓ DIG tests
✓ Wrapper tests
✓ Submission schema
✓ Coordinated smoke test
✓ Expected outputs
✓ Metadata/provenance
✓ Legacy comparison: 216/216 set-equivalent
✓ Run receipt generated
✓ Adoption status: READY

Ready for submission.
```

Failure example:

```text
Adoption verification: FAILED

✓ Workspace safety
✓ Dependencies resolved
✓ Wrapper-only architecture
✓ DIG tests
✗ Legacy comparison

4 of 216 gene sets differ.

Report:
  adoption/comparison_report.tsv

Next:
  Review the comparison report and correct the migration.
```

Store verification result in `.adoption-workspace.yaml`.

Do not permit `submit-adoption` unless the last relevant verification passes and the workspace has not changed in a way that invalidates that result.

---

# Command 3: `submit-adoption`

Add:

```bash
python3 -m submission_tools submit-adoption \
    --workspace ~/gene-set-adoptions/my_library
```

This command prepares and opens pull requests after successful verification.

It should stop at draft PR creation.

It must never merge PRs.

---

# Submission Preconditions

Before any commit or push:

```text
✓ adoption status READY
✓ latest verification PASS
✓ workspace safety checks still pass
✓ legacy source unchanged
✓ both repositories on adoption branches
✓ no unresolved dependency gaps
✓ no credentials detected
✓ no large source datasets staged
✓ origin is contributor fork
✓ upstream is canonical repository
```

If verification is stale because files changed after the last verification, fail and tell the user to run:

```bash
python3 -m submission_tools verify-adoption --workspace ...
```

again.

---

# Detect Which Repositories Changed

Determine separately:

```text
DIG changes: yes/no
Wrapper changes: yes/no
```

If DIG has no changes because the adopted library fully reuses existing DIG functionality, do not create an unnecessary DIG PR.

The wrapper PR should then record that no paired DIG PR is required, according to the existing schema convention.

---

# Show Submission Summary Before Proceeding

Print:

```text
Changes to submit

dig-gene-set-extractors:
  7 files changed
  +421 / -18

geneset-extractor-dev:
  12 files changed
  +583 / -4

No source datasets detected in Git changes.

Target upstream base:
  rk-submission-system-v1

Proceed with submission? [y/N]
```

This should be the one normal user confirmation before code leaves the machine.

Provide a noninteractive flag only for advanced automation, e.g.:

```text
--yes
```

---

# Safe Staging

Do not blindly run:

```bash
git add .
```

Instead:

1. Inspect changed/untracked files.
2. Classify them.
3. Reject:
   - credentials;
   - secrets;
   - environment tokens;
   - large source data;
   - venvs;
   - caches;
   - logs;
   - unrelated files.
4. Stage only expected contribution paths.

If a suspicious file exists, stop and show it.

---

# Automatic Commits

If DIG changed:

```text
Add extractor support for my_library
```

If wrapper changed:

```text
Add my_library gene-set library
```

Allow commit-message overrides, but use sensible defaults.

Do not amend unrelated existing commits.

---

# Automatic DIG Commit Pinning

After the DIG contribution commit is created:

```bash
git rev-parse HEAD
```

Use that exact full SHA to update the wrapper submission:

```yaml
dig:
  commit: <40-character-sha>
```

Then rerun coordinated validation before pushing.

If this update changes the wrapper working tree, include it in the wrapper contribution commit.

---

# Push Only to Contributor Forks

Push:

```text
adopt/my_library
```

to `origin` only.

Never push to `upstream`.

Before push, re-check that origin matches the expected fork from `.adoption-workspace.yaml`.

Example conceptual command:

```bash
git push -u origin adopt/my_library
```

---

# GitHub CLI PR Automation

If `gh` is installed and authenticated, open draft PRs automatically.

Use `gh auth status` to confirm authentication.

Do not fail the entire submission if `gh` is unavailable.

---

# DIG PR

If DIG changed:

Head:

```text
USERNAME:adopt/my_library
```

Base repository:

```text
flannick/dig-gene-set-extractors
```

Current base branch:

```text
rk-submission-system-v1
```

Create a draft PR.

Generate a PR body automatically from:

- library ID;
- source metadata;
- adoption report;
- DIG changes;
- tests;
- smoke result;
- legacy comparison summary.

Example title:

```text
Add extractor support for my_library
```

---

# Wrapper PR

Head:

```text
USERNAME:adopt/my_library
```

Base repository:

```text
broadinstitute/geneset-extractor-dev
```

Current base branch:

```text
rk-submission-system-v1
```

Create a draft PR.

Example title:

```text
Add my_library gene-set library
```

The body should include:

- adopted legacy library;
- source/release;
- DIG PR URL if applicable;
- pinned DIG SHA;
- reproduction result;
- smoke result;
- legacy comparison result;
- adoption status;
- any documented intentional differences.

---

# Paired PR Metadata

If DIG PR exists, update:

```yaml
paired_pull_requests:
  dig_gene_set_extractors: <DIG_PR_URL>
```

After wrapper PR exists, update:

```yaml
paired_pull_requests:
  geneset_extractor_dev: <WRAPPER_PR_URL>
```

This may require one small follow-up wrapper commit after the wrapper PR has been opened.

That is acceptable.

The tool should:

1. update `submission.yaml`;
2. commit:
   ```text
   Record paired pull request URLs
   ```
3. push to the wrapper fork;
4. optionally rerun lightweight validation.

The open PR updates automatically.

---

# No-DIG-Changes Case

If DIG has no contribution changes:

- do not create a DIG PR;
- keep the tested DIG commit pin;
- record the schema-approved equivalent of:
  ```text
  N/A
  ```
  for the DIG paired PR;
- open only the wrapper PR.

Do not invent a meaningless DIG PR just to satisfy pairing.

---

# Fallback When `gh` Is Unavailable

Do not fail after successful push.

Print exact compare/PR URLs or enough information to create them manually.

Example:

```text
Branches pushed successfully.

Create DIG PR:
  upstream: flannick/dig-gene-set-extractors
  base: rk-submission-system-v1
  head: USERNAME:adopt/my_library

Create wrapper PR:
  upstream: broadinstitute/geneset-extractor-dev
  base: rk-submission-system-v1
  head: USERNAME:adopt/my_library
```

If useful, add options:

```bash
--dig-pr URL
--wrapper-pr URL
```

so the contributor can rerun `submit-adoption` to record manually created PR URLs.

---

# Submission Output

Successful example:

```text
Submission prepared successfully.

DIG PR:
  https://github.com/flannick/dig-gene-set-extractors/pull/123

Wrapper PR:
  https://github.com/broadinstitute/geneset-extractor-dev/pull/456

Pinned DIG commit:
  0123456789abcdef0123456789abcdef01234567

Both pull requests were opened as drafts.

Next:
  Wait for CI and reviewer feedback.
```

---

# Current Development Base

For the current implementation/testing period:

```text
base branch = rk-submission-system-v1
```

Do not automatically target `main`.

Design the base branch as configurable in `.adoption-workspace.yaml` so that once the submission system is merged, the default can be changed to:

```text
main
```

without redesigning the workflow.

---

# CLI Summary

Normal user flow:

## 1. Adopt

```bash
python3 -m submission_tools adopt \
    --existing /path/to/legacy_submission \
    --library-id my_library \
    --workspace ~/gene-set-adoptions/my_library \
    --github-user USERNAME
```

## 2. AI interaction

```bash
cd ~/gene-set-adoptions/my_library
codex
```

Tell the agent:

```text
Follow AI_ADOPTION_PROMPT.md.
```

## 3. Verify

```bash
python3 -m submission_tools verify-adoption \
    --workspace ~/gene-set-adoptions/my_library
```

## 4. Submit

```bash
python3 -m submission_tools submit-adoption \
    --workspace ~/gene-set-adoptions/my_library
```

This is the intended contributor experience.

---

# Keep Low-Level Commands

Do not remove existing advanced commands.

Continue supporting:

```text
validate
discover
scaffold
adopt
compare-legacy
adoption-status
```

`verify-adoption` and `submit-adoption` should orchestrate these lower-level components.

Avoid duplicating validation logic.

---

# Testing Requirements

Add tests for at least:

## Workspace creation

- fresh workspace creation;
- unsafe nested workspace rejection;
- workspace inside existing repo rejection;
- workspace == legacy path rejection;
- contributor fork cloning;
- upstream remote configuration;
- adoption branch creation;
- workspace manifest generation.

## Safety

- origin must be fork by default;
- upstream is canonical;
- push-to-upstream attempts are impossible through normal code path;
- legacy source remains unchanged;
- legacy hash changes are detected;
- wrong branch is rejected;
- wrong workspace repo path is rejected.

## Verify

- dirty DIG auto-selects development validation mode;
- clean DIG uses exact commit validation;
- failed wrapper validation blocks verification;
- failed smoke blocks verification;
- legacy mismatch blocks verification when comparison is strict;
- report-only comparison does not block solely for differences;
- run receipt generated;
- READY status produced only when all requirements pass.

## Submission

- stale verification blocks submit;
- DIG-only changes;
- wrapper-only changes;
- both repos changed;
- no-DIG-change path avoids DIG PR;
- safe staging;
- secret-like files rejected;
- large-data files rejected;
- exact DIG SHA pinned;
- push only to origin;
- PR metadata updated.

## GitHub CLI

Mock `gh`.

Test:

- authenticated `gh`;
- unauthenticated `gh`;
- `gh` unavailable;
- DIG PR creation;
- wrapper PR creation;
- draft PR behavior;
- paired PR URL recording;
- fallback instructions.

Do not require real GitHub network access in unit tests.

Use temporary local Git repositories and mocks.

---

# Documentation

Add or update a concise contributor page such as:

```text
docs/submissions/adopting-existing-library.md
```

The normal user-facing instructions should be short:

```text
1. Fork both repositories.
2. Run `adopt`.
3. Start your AI agent in the generated workspace and tell it to follow `AI_ADOPTION_PROMPT.md`.
4. Run `verify-adoption`.
5. Run `submit-adoption`.
6. Review the draft PRs and CI results.
```

Move detailed manual/debugging instructions to an advanced section.

---

# Critical Acceptance Criteria

Do not consider this implementation complete unless:

- adoption occurs entirely inside a user-specified isolated workspace;
- fresh clones are used;
- contributor forks are writable origins by default;
- canonical repositories are upstream remotes;
- no normal code path pushes upstream;
- the original legacy submission remains unchanged;
- the user's unrelated existing local clones remain unchanged;
- AI instructions are generated inside the workspace;
- verification requires only `--workspace`;
- submission requires only `--workspace`;
- DIG commit pinning is automatic;
- paired PR metadata is automatic;
- draft PRs can be opened automatically with `gh`;
- lack of `gh` degrades gracefully;
- no-DIG-change submissions require only the wrapper PR;
- existing low-level commands remain supported;
- current `rk-submission-system-v1` behavior remains backward-compatible;
- CI and human review still remain the final authority;
- `submit-adoption` never merges PRs.
