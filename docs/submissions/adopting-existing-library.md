# Adopting an existing library

Use this path when gene sets were produced outside the submission framework.
It does not provide a weaker legacy standard. The normal workflow creates a
fresh, isolated workspace containing contributor-fork clones of both
repositories; it never changes the original legacy directory or unrelated
local checkouts.

```bash
python3 -m submission_tools adopt \
  --existing /path/to/old_library \
  --library-id MY_LIBRARY \
  --workspace ~/gene-set-adoptions/MY_LIBRARY \
  --github-user USERNAME
```

1. Fork both repositories first. The tool uses those forks as writable
   `origin` remotes and configures the canonical repositories as read-only
   `upstream` remotes. It uses upstream `main` as the default baseline and PR
   target; pass `--base-branch SOME_BRANCH` only when an alternate baseline is
   explicitly required.
2. Run `adopt` as above. It creates branches named `adopt/MY_LIBRARY`, an
   inventory, legacy-output checksums, and `AI_ADOPTION_PROMPT.md`.
3. Start a coding agent in the generated workspace and tell it to follow that
   prompt. Every intermediate must be either a declared source input or
   produced by committed code. Substantive processing, statistics, mapping,
   ranking, and gene-set construction belong in `dig-gene-set-extractors`; this
   repository remains wrapper-only.
4. Verify the migration:

```bash
python3 -m submission_tools verify-adoption \
  --workspace ~/gene-set-adoptions/MY_LIBRARY
```

5. Review the result, then commit/push to your forks and open draft PRs:

```bash
python3 -m submission_tools submit-adoption \
  --workspace ~/gene-set-adoptions/MY_LIBRARY --yes
```

`submit-adoption` never pushes to `upstream`, never merges pull requests, and
refuses secret-like files, large source data, and stale verification. When
`gh` is installed and authenticated it opens draft PRs; otherwise it prints the
branch details needed to create PRs manually.

## Maintainer testing without forks

Forks remain the normal contributor workflow. A repository maintainer testing
in an isolated workspace may explicitly use the canonical repositories as
`origin`:

```bash
python3 -m submission_tools adopt \
  --existing /path/to/old_library \
  --library-id MY_LIBRARY \
  --workspace ~/gene-set-adoptions/MY_LIBRARY \
  --dig-fork https://github.com/flannick/dig-gene-set-extractors.git \
  --wrapper-fork https://github.com/broadinstitute/geneset-extractor-dev.git \
  --allow-upstream-origin
```

This remains a fresh clone on `adopt/MY_LIBRARY`, never `main`, and records the
override in `.adoption-workspace.yaml`. Verification accepts canonical origins
only when that recorded override exists. Submission requires a second explicit
acknowledgement:

```bash
python3 -m submission_tools submit-adoption \
  --workspace ~/gene-set-adoptions/MY_LIBRARY --yes --allow-upstream-origin
```

That second flag is not inferred from the workspace. Draft PRs in this mode are
same-repository branch PRs: `adopt/MY_LIBRARY` into upstream `main`.

## Advanced / low-level commands

The existing lower-level commands remain available for debugging and unusual
workflows:

After migration, run ordinary validation and compare outputs:

```bash
python3 -m submission_tools adopt --existing ../old_library --library-id MY_LIBRARY --output MY_LIBRARY
python3 -m submission_tools validate --submission MY_LIBRARY/submission.yaml --dig-repo ../dig-gene-set-extractors --smoke --receipt-out MY_LIBRARY/run_receipt.json
python3 -m submission_tools compare-legacy --library MY_LIBRARY
python3 -m submission_tools adoption-status --library MY_LIBRARY
```

`READY` never bypasses normal submission validation. Use the usual paired-PR
and review process after the migration is complete.
