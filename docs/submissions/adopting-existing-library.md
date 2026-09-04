# Adopting an existing library

Use this path when gene sets were produced outside the submission framework.
It does not provide a weaker legacy standard. The normal workflow creates a
fresh, isolated workspace containing contributor-fork clones of both
repositories; it never changes the original legacy directory or unrelated
local checkouts.

For the complete maintainer procedure—including `exact_reproduction` versus
`scientific_reimplementation`, preserving an earlier adoption branch, and
workspace-local runtime artifacts—read
[adopting-trusted-existing-submission.md](adopting-trusted-existing-submission.md).

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

## Repository ignore policy

The wrapper repository may use a deny-by-default root `.gitignore`. Each
adoption workspace therefore creates `adoption/gitignore_allowlist.md` with
library-specific rules for committed code, configuration, manifests, and small
fixtures. Review and apply that snippet to the wrapper root `.gitignore`
before `./submit-adoption`.

Do not use `git add -f`. Keep `inputs/`, `outputs/`, `work/`, and
`run_receipt.json` ignored. Submission tooling preflights this policy,
rejects ignored submission source files, and never stages generated library
artifacts even if a local ignore rule was accidentally loosened.

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

Each adopted library has one canonical local execution path:

```text
<Library>/run/build_<library>_genesets.sh
<Library>/config/task_manifest.tsv
```

The builder dispatches one declared task (or smoke selection) to the pinned
DIG workflow. It is the path used by `reproduction/reproduce.sh`; do not add a
second library-local `run/submit_models.sh` convention. When the library needs
cluster execution, adoption also creates a thin root-level adapter:

```text
run/submit_<library>_models_cluster.sh
run/submit_<library>_models_cluster_apptainer.sh
run/submit_library_models_cluster.sh
run/submit_library_models_cluster_apptainer.sh
```

The per-library adapters delegate to their corresponding shared native or
Apptainer launcher. Both read `task_manifest.tsv`, write a filtered worklist
by default, and submit a scheduler array only when passed `--submit`; neither
owns scientific processing or output formatting. Set `SUBMISSION_WORK_DIR` (or
the explicit `WORK_ROOT` scheduler override) to a location outside the wrapper
checkout before using either launcher.

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
      regenerated: outputs/full/genesets.gmt
      comparison: set_equivalent
      scope: full
```

The regenerated path is a safe, repository-relative *logical* output path.
New isolated adoption workspaces resolve it beneath `$WORKSPACE/work`, not
beneath the wrapper checkout: their launchers receive
`SUBMISSION_WORK_DIR=$WORKSPACE/work`. For example, a declared
`outputs/full/genesets.gmt` is written to
`$WORKSPACE/work/outputs/full/genesets.gmt`. Without a declared full mapping,
verification reports that smoke passed and that full equivalence was not run;
submission remains blocked until the required full comparison is completed. An
explicit `scope: smoke` mapping is allowed for a corresponding smoke reference,
but is never selected automatically for a full legacy GMT.

The implementation agent must run full reproduction with the same isolated
artifact location before it reports completion. Do not write downloaded inputs,
generated GMTs, provenance sidecars, or run receipts into a submitted library
directory. The workspace `work/` and `reports/` directories are untracked
execution locations.

To preserve one run while validating another, choose a distinct artifact
directory and pass the same directory to verification:

```bash
cd "$WORKSPACE/geneset-extractor-dev/MY_LIBRARY"
SUBMISSION_WORK_DIR="$WORKSPACE/work-rerun-20260902" bash reproduction/reproduce.sh full
cd "$WORKSPACE"
./verify-adoption --work-dir work-rerun-20260902
```

`--work-dir` must remain beneath the workspace and outside the DIG, wrapper,
legacy, and reports directories. It never clears an existing directory.

## Independent legacy implementations and close reimplementations

When a legacy library was developed outside this architecture, use its scripts
as read-only scientific evidence and recreate its substantive logic in DIG.
Do not submit those scripts as wrapper runtime code. If a historical public
input release cannot be recovered, declare
`adoption.comparison_policy.mode: scientific_reimplementation`, document the
evidence in `adoption/source_assessment.md`, and use explicit, predeclared
scientific-comparability metrics and set mappings. A passing result is reported
as **scientifically comparable; not set-equivalent** and requires an approving
maintainer reference before a ready submission can pass. Exact reproductions
continue to use the existing `set_equivalent` comparison unchanged.

## Advanced / low-level commands

The existing lower-level commands remain available for debugging and unusual
workflows:

After migration, run ordinary validation and compare outputs:

```bash
python3 -m submission_tools adopt --existing ../old_library --library-id MY_LIBRARY --output MY_LIBRARY
python3 -m submission_tools validate --submission MY_LIBRARY/submission.yaml --dig-repo ../dig-gene-set-extractors --smoke --receipt-out MY_LIBRARY/run_receipt.json
python3 -m submission_tools verify-adoption --workspace ~/gene-set-adoptions/MY_LIBRARY --work-dir work-rerun-20260902
python3 -m submission_tools submit-adoption --workspace ~/gene-set-adoptions/MY_LIBRARY --yes
python3 -m submission_tools compare-legacy --library MY_LIBRARY
python3 -m submission_tools adoption-status --library MY_LIBRARY
```

`READY` never bypasses normal submission validation. Use the usual paired-PR
and review process after the migration is complete.
