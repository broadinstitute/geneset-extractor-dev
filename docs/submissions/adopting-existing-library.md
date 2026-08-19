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
   repository remains wrapper-only. The generated prompt includes a mandatory
   completion gate: it requires concrete DIG metadata, no scaffold `TODO`
   values, explicit full legacy-to-regenerated mappings, separate smoke/full
   output contracts, and source provenance overlays before an adoption can be
   reported complete.

## Target architecture for an adopted library

The generated `AI_ADOPTION_PROMPT.md` uses GTEx, MoTrPAC, HuBMAP, and
LINCS_L1000 as references for wrapper naming and orchestration structure, not
as permission to preserve historical analytical implementation in the wrapper.
The target wrapper layout is small and explicit:

```text
<Library>/config/        model, partition, manifest, and description configuration
<Library>/run/           strict shell launcher
<Library>/src/           selection and DIG dispatch only
<Library>/reproduction/  declared input and reproduction contract
<Library>/expected/      expected-output manifest
<Library>/tests/fixtures/ small redistributable smoke fixtures
```

All substantive data processing and gene-set generation logic belongs in
`dig-gene-set-extractors`. `geneset-extractor-dev` may configure, dispatch,
execute, refresh, and publish that logic, but must not independently implement
it. The prompt identifies the selected `--pattern` (`gtex`, `motrpac`,
`hubmap`, `lincs_l1000`, or `generic`) and directs the agent to the existing
DIG submission contract before it creates a wrapper dispatcher.
4. Verify the migration from the workspace root. This helper deliberately uses
   the `submission_tools` code in the workspace's `geneset-extractor-dev`
   clone, so it cannot silently use another checkout or installed package:

```bash
cd ~/gene-set-adoptions/MY_LIBRARY
./verify-adoption
```

This verification also runs `provenance_complete` after smoke reproduction.
Ready adopted libraries require a declared full provenance contract and a
source-input → workflow → geneset → materialized-output graph without local
contributor paths.

### Source provenance

For each adopted source, keep its stable URI/identifier in
`reproduction/input_manifest.tsv` and add corresponding metadata to
`config/provenance_overlay.json`. Pass that overlay to the supporting DIG
entry point when it supports `--provenance_overlay_json`. Do not map a whole
home directory, the adoption workspace, or outputs to a provider URL with
`--provenance_mirror_local_prefix`; those locations contain local execution
paths, not remotely hosted source data.

5. Review the result, then commit/push to your forks and open draft PRs:

```bash
./submit-adoption --yes
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
./submit-adoption --yes --allow-upstream-origin
```

That second flag is not inferred from the workspace. Draft PRs in this mode are
same-repository branch PRs: `adopt/MY_LIBRARY` into upstream `main`.

## Full legacy equivalence

Smoke reproduction proves that the small test workflow runs; it is not treated
as a full-library comparison. Declare an explicit regenerated counterpart for
each legacy output that must be compared, for example in `submission.yaml`:

```yaml
adoption:
  reference_outputs:
    - legacy: /read-only/legacy/genesets.gmt
      regenerated: work/full/genesets.gmt
      comparison: set_equivalent
      scope: full
```

The regenerated path is relative to the submitted library. Without a declared
full mapping, verification reports that smoke passed and that full equivalence
was not run; submission remains blocked until the required full comparison is
completed. An explicit `scope: smoke` mapping is allowed for a corresponding
smoke reference, but is never selected automatically for a full legacy GMT.

## Advanced / low-level commands

The existing lower-level commands remain available for debugging and unusual
workflows:

After migration, run ordinary validation and compare outputs:

```bash
python3 -m submission_tools adopt --existing ../old_library --library-id MY_LIBRARY --output MY_LIBRARY
python3 -m submission_tools validate --submission MY_LIBRARY/submission.yaml --dig-repo ../dig-gene-set-extractors --smoke --receipt-out MY_LIBRARY/run_receipt.json
python3 -m submission_tools verify-adoption --workspace ~/gene-set-adoptions/MY_LIBRARY
python3 -m submission_tools submit-adoption --workspace ~/gene-set-adoptions/MY_LIBRARY --yes
python3 -m submission_tools compare-legacy --library MY_LIBRARY
python3 -m submission_tools adoption-status --library MY_LIBRARY
```

`READY` never bypasses normal submission validation. Use the usual paired-PR
and review process after the migration is complete.
