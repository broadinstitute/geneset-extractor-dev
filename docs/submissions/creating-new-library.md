# Creating a new library in an isolated workspace

Use this workflow for a brand-new source library. It creates fresh clones of
your DIG and wrapper forks, on `submit/<library_id>` branches based on upstream
`main`; it never changes the source-input path or unrelated local checkouts.

```bash
python3 -m submission_tools create-library \
  --inputs /path/to/source-inputs \
  --library-id MY_LIBRARY \
  --workspace ~/gene-set-submissions/MY_LIBRARY \
  --github-user USERNAME

cd ~/gene-set-submissions/MY_LIBRARY
codex
```

Tell the agent: `Follow AI_NEW_LIBRARY_PROMPT.md completely.` The prompt
requires an `reports/AI_NEW_LIBRARY_PLAN.md` before material scientific
decisions, keeps source inputs read-only, and directs substantive parsing,
analysis, mapping, ranking, and gene-set construction to DIG.

The workspace records input paths, sizes, and SHA-256 checksums in
`inputs/input_inventory.json`; source data is not copied into either Git
repository. It also generates the submission scaffold and populates its input
manifest with the observed sources. Replace the generated release, access, and
license placeholders before ready review.

After implementation, use the workspace-local helpers:

```bash
./verify-library
./submit-library --yes
```

`verify-library` validates workspace remotes/branches, confirms source inputs
did not change, checks wrapper schema and boundaries, validates the declared
DIG checkout and identifiers, runs the explicitly local smoke command, and
writes a receipt. It also runs `provenance_complete` against declared smoke and
full provenance contracts; ready submissions require complete full provenance.
It never runs this flow in CI and never downloads inputs.
`submit-library` refuses stale verification, direct upstream pushes, unsafe
files, and missing Git author identity. It commits/pushes only the work branch
to `origin` and opens draft PRs when `gh` is available; it never merges.

## Maintainer testing without forks

Forks remain the normal workflow. A maintainer may use canonical repositories
as `origin` only with the explicit override:

```bash
python3 -m submission_tools create-library \
  --inputs /path/to/source-inputs \
  --library-id MY_LIBRARY \
  --workspace ~/gene-set-submissions/MY_LIBRARY \
  --dig-fork https://github.com/flannick/dig-gene-set-extractors.git \
  --wrapper-fork https://github.com/broadinstitute/geneset-extractor-dev.git \
  --allow-upstream-origin

./submit-library --yes --allow-upstream-origin
```

The override is recorded at creation and must be supplied again before push.
The tool rejects an existing remote `submit/<library_id>` branch; choose a
different `--work-branch` or explicitly resume the existing workspace.
