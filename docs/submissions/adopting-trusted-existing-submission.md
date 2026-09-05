# Adopt a trusted existing submission

Use this maintainer-focused guide when a legacy gene-set library is believed to
be scientifically correct and complete, but was produced outside the current
DIG-plus-wrapper architecture. The legacy directory remains read-only; the
result is developed in fresh, isolated clones.

All substantive data processing and gene-set generation logic belongs in
`dig-gene-set-extractors`. `geneset-extractor-dev` may configure, dispatch,
execute, refresh, and publish that logic, but must not independently implement
it.

Choose the acceptance mode before starting:

- **`exact_reproduction`** requires set-equivalent full regenerated GMTs.
- **`scientific_reimplementation`** is for unrecoverable historical inputs or
  independently developed implementations. It requires documented source
  uncertainty, declared comparability metrics, and scientific review before a
  submission can be ready.

The normal contributor workflow uses forks. This guide demonstrates the
explicit maintainer/test override, in which same-repository
`adopt/<library_id>` branches target canonical `main`.

## Short version: `exact_reproduction`

```bash
export LEGACY="/absolute/path/to/existing_submission"
export LIBRARY_ID="MY_LIBRARY"
export WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID"
export WORK_DIR="$WORKSPACE/out"
export DIG_BRANCH="main"
export WRAPPER_BRANCH="main"

git clone --branch "$WRAPPER_BRANCH" \
  https://github.com/broadinstitute/geneset-extractor-dev.git \
  submission-system-tools

cd submission-system-tools
python3 -m submission_tools adopt \
  --existing "$LEGACY" \
  --library-id "$LIBRARY_ID" \
  --workspace "$WORKSPACE" \
  --dig-fork https://github.com/flannick/dig-gene-set-extractors.git \
  --wrapper-fork https://github.com/broadinstitute/geneset-extractor-dev.git \
  --allow-upstream-origin \
  --dig-base-branch "$DIG_BRANCH" \
  --wrapper-base-branch "$WRAPPER_BRANCH"

cd "$WORKSPACE"
codex
```

Tell Codex:

```text
Follow AI_ADOPTION_PROMPT.md completely.

This is an exact_reproduction adoption. The acceptance criterion is exact,
set-equivalent full regenerated output. Do not downgrade this to
scientific_reimplementation unless you first document why exact reproduction
is impossible.

This legacy submission is believed to be scientifically correct and complete.
Preserve its scientific behavior. Make sure each authoritative full legacy GMT
is explicitly mapped to its full regenerated counterpart for set-equivalent
comparison.

You are authorized to identify released inputs, complete input_manifest.tsv
with real identifiers, versions, URLs/access instructions, and feasible
checksums, and download public inputs required for full reproduction. Run full
reproduction and every declared full comparison. Keep downloaded inputs and
generated outputs untracked. Do not stop after smoke validation or leave
ordinary manifest placeholders; use allowed draft values such as TBD where
needed. Report each controlled-access or unavailable input with its exact
identifier and access blocker.

Use SUBMISSION_WORK_DIR="$WORK_DIR" for smoke and full reproduction. Write
generated outputs and provenance sidecars beneath that directory, never under
geneset-extractor-dev/<library_id>.
```

Before final verification, apply the reviewed allowlist so the wrapper can
stage code and configuration without staging inputs or generated artifacts:

```bash
cd "$WORKSPACE/geneset-extractor-dev"
sed -n '1,240p' ../adoption/gitignore_allowlist.md
printf '\n' >> .gitignore
cat ../adoption/gitignore_allowlist.md >> .gitignore
```

Then validate the artifacts Codex generated:

```bash
cd "$WORKSPACE"
./verify-adoption --work-dir "$WORK_DIR"
./submit-adoption --yes --allow-upstream-origin
```

Submit only after verification reports `PASS` and the declared full comparisons
have completed.

## Short version: `scientific_reimplementation`

Use the same setup commands, but give Codex this instruction instead:

```text
Follow AI_ADOPTION_PROMPT.md completely.

This is a scientific_reimplementation adoption. Treat legacy code and GMTs as
read-only evidence of the scientific method, not code to copy.

Preserve intended biological meaning and defensible scientific decisions.
Recreate substantive preprocessing, normalization, statistics, gene mapping,
ranking, and GMT generation in dig-gene-set-extractors. Keep
geneset-extractor-dev limited to configuration, dispatch, reproduction,
metadata/provenance refresh, and publishing.

Use the best publicly available inputs. When exact historical releases are not
available, document source-version uncertainty and expected impact in
adoption/source_assessment.md. Complete input_manifest.tsv with real source
metadata and, for every full input, source_version_confidence and
legacy_input_relationship.

Configure submission.yaml for scientific_reimplementation with a documented
reason, source assessment, explicit full legacy-to-regenerated mappings,
scientific_comparability comparisons, justified named-set/Jaccard thresholds,
and a one-to-one set-name mapping when names differ. Do not claim exact or
set-equivalent reproduction unless supported by results.

Run full reproduction and every declared scientific-comparability comparison.
Keep downloaded inputs and generated outputs untracked. Report each
controlled-access, unavailable, or scientifically ambiguous input with its
identifier, access blocker, and validation impact. Do not bypass the
DIG-based implementation requirement.

Use SUBMISSION_WORK_DIR="$WORK_DIR" for smoke and full reproduction. Write
generated outputs and provenance sidecars beneath that directory, never under
geneset-extractor-dev/<library_id>.
```

Before final verification, also apply the reviewed generated allowlist (the
same commands shown in the `exact_reproduction` short version). Do not use
`git add -f`; the allowlist keeps `inputs/`, `outputs/`, `work/`, and
`run_receipt.json` ignored.

Run the same `./verify-adoption --work-dir "$WORK_DIR"` command. A draft may
have a pending scientific review; a ready scientific reimplementation requires
an approved GitHub PR or issue reference in `submission.yaml`.

## Preserve an earlier adoption attempt

Do this before reusing an existing `adopt/<library_id>` branch name. Renaming
the branch preserves the earlier work without changing its commits. Replace
the example names below with your library ID and chosen version suffix.

```bash
cd "$WORKSPACE/dig-gene-set-extractors"
git checkout adopt/MY_LIBRARY
git branch -m adopt/MY_LIBRARY-v1
git push -u origin adopt/MY_LIBRARY-v1
git push origin --delete adopt/MY_LIBRARY

cd "$WORKSPACE/geneset-extractor-dev"
git checkout adopt/MY_LIBRARY
git branch -m adopt/MY_LIBRARY-v1
git push -u origin adopt/MY_LIBRARY-v1
git push origin --delete adopt/MY_LIBRARY
```

Do not delete the old remote branch until the replacement branch exists on
`origin`. If an open PR uses the old branch, preserve or close that PR
deliberately before deleting its head branch.

## Full tutorial

### 1. Define the workspace

```bash
export LEGACY="/absolute/path/to/existing_submission"
export LIBRARY_ID="MY_LIBRARY"
export WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID"
export WORK_DIR="$WORKSPACE/out"
export DIG_BRANCH="main"
export WRAPPER_BRANCH="main"
```

`WORKSPACE` must be separate from `LEGACY`, outside any Git repository, and
empty when `adopt` starts. `WORK_DIR` must stay beneath the workspace but
outside `dig-gene-set-extractors/`, `geneset-extractor-dev/`, `legacy/`, and
`reports/`. It is persistent and is never cleared by verification.

The wrapper tooling checkout must use `WRAPPER_BRANCH`. `DIG_BRANCH` and
`WRAPPER_BRANCH` may be different: each must exist on its corresponding
canonical upstream. `--base-branch` remains a convenient common fallback, but
`--dig-base-branch` and `--wrapper-base-branch` independently override it.
After merge, return both to `main`.

### 2. Obtain tooling and create the isolated workspace

```bash
git clone --branch "$WRAPPER_BRANCH" \
  https://github.com/broadinstitute/geneset-extractor-dev.git \
  submission-system-tools

cd submission-system-tools
python3 -m submission_tools adopt \
  --existing "$LEGACY" \
  --library-id "$LIBRARY_ID" \
  --workspace "$WORKSPACE" \
  --dig-fork https://github.com/flannick/dig-gene-set-extractors.git \
  --wrapper-fork https://github.com/broadinstitute/geneset-extractor-dev.git \
  --allow-upstream-origin \
  --dig-base-branch "$DIG_BRANCH" \
  --wrapper-base-branch "$WRAPPER_BRANCH"
```

This creates fresh clones, read-only legacy inventory and reference data,
workspace-local `./verify-adoption` and `./submit-adoption` helpers, and
`adopt/$LIBRARY_ID` branches. It never modifies `LEGACY` or works directly on
`main`.

Inspect the result:

```bash
cd "$WORKSPACE"
cat .adoption-workspace.yaml
find adoption -maxdepth 1 -type f -print | sort
```

Confirm the manifest records the expected DIG and wrapper baselines, work
branches, remotes, and maintainer upstream-origin override.

### 3. Complete the migration with Codex

Run `codex` from `$WORKSPACE`, select either the exact or scientific prompt
above, and include it after `Follow AI_ADOPTION_PROMPT.md completely.`

Codex must inspect the inventory, dependency map, legacy reference GMTs, and
the available DIG submission contracts before changing code. It must:

1. place substantive reusable logic, fixtures, and tests in DIG;
2. keep the wrapper thin and declarative;
3. declare every source and fixture in `input_manifest.tsv`;
4. add source-aware DIG provenance rather than constructing graphs in the
   wrapper;
5. honor `SUBMISSION_WORK_DIR="$WORK_DIR"` for smoke and full runs;
6. run smoke, full reproduction, and the explicitly declared full comparison;
7. keep inputs, generated artifacts, and receipts untracked.

The output-manifest `relative_path` values remain safe logical paths. In an
isolated adoption workspace they resolve beneath `WORK_DIR`. For example,
`outputs/full/genesets.gmt` resolves to
`$WORK_DIR/outputs/full/genesets.gmt`.

### 4. Apply the reviewed wrapper ignore allowlist

The wrapper repository intentionally uses a deny-by-default `.gitignore`.
Before the final verification, review and append the library-specific allowlist
that `adopt` generated. This permits only committed source/configuration files;
it does not permit inputs, generated outputs, runtime work, or receipts.

```bash
cd "$WORKSPACE/geneset-extractor-dev"
sed -n '1,240p' ../adoption/gitignore_allowlist.md
printf '\n' >> .gitignore
cat ../adoption/gitignore_allowlist.md >> .gitignore
```

Confirm source files are no longer ignored (the first command should print no
matching rule) while generated artifacts remain ignored (the second command
should print matching ignore rules):

```bash
git check-ignore -v \
  "$LIBRARY_ID/submission.yaml" \
  "$LIBRARY_ID/config/model_list.tsv" \
  "$LIBRARY_ID/reproduction/download_inputs.sh"

git check-ignore -v \
  "$LIBRARY_ID/inputs/example.tsv" \
  "$LIBRARY_ID/outputs/example.gmt" \
  "$LIBRARY_ID/run_receipt.json"
```

Do not use `git add -f`. The `.gitignore` update is an intentional wrapper PR
change and must be included in the final verification digest.

### 5. Verify the completed migration

Codex should already have run the full reproduction. Do not rerun it merely to
verify. Instead, validate the generated artifacts with the workspace-local
tooling:

```bash
cd "$WORKSPACE"
./verify-adoption --work-dir "$WORK_DIR"
```

This runs smoke reproduction using the same runtime directory, validates the
wrapper and declared DIG interface, checks smoke/full provenance contracts,
and evaluates only explicit legacy-to-regenerated mappings. It records the
selected work directory in workspace verification metadata and the run receipt
under `reports/`.

For an exact reproduction, a successful full comparison reports set-equivalent
gene sets. For a scientific reimplementation, success means the declared
comparability thresholds passed; it does not claim set equivalence.

If verification fails, restart Codex from `$WORKSPACE`, give it the output,
and require it to fix the migration without silently changing scientific
parameters or comparing a full legacy GMT with a smoke output. Re-run only
`./verify-adoption --work-dir "$WORK_DIR"` after Codex has repaired the work.

### 6. Review and submit

Inspect comparison reports in `adoption/` and the receipt in `reports/`:

```bash
find adoption -maxdepth 1 -type f -name 'comparison*' -print
find reports -maxdepth 1 -type f -name '*receipt*.json' -print
```

Preview submission first:

```bash
./submit-adoption --allow-upstream-origin
```

After a passing, current verification:

```bash
./submit-adoption --yes --allow-upstream-origin
```

The second override is intentional. The tool commits and pushes only the
`adopt/$LIBRARY_ID` branch to `origin`, never directly to `main` or `upstream`,
and never merges a PR. It pins the exact DIG commit in the wrapper manifest,
opens draft PRs when `gh` is authenticated, and creates a DIG PR only when the
DIG branch has changes.

Review the draft PRs and wait for the required checks. Do not merge a
submission with unexplained validation failures.

## Related documentation

Read [adopting-existing-library.md](adopting-existing-library.md) for the
architecture, provenance, ignore-policy, and low-level command contract.
Read [review-policy.md](review-policy.md) before approving a submission.
