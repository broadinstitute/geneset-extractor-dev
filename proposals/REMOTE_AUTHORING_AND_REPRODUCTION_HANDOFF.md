# Remote authoring and reproduction handoff

## Purpose

An adoption may require a full source-data reproduction that is inappropriate
for the machine used by an interactive coding agent.  This proposal separates
the two roles without weakening the existing adoption contract:

* a local **authoring host** creates DIG and thin-wrapper code and
  configuration using a small deterministic fixture explicitly supplied by the
  user;
* a **reproduction host** (usually an HPC/login host) obtains declared inputs,
  runs the full workflow or explicit scheduler launchers, performs full
  comparison/provenance validation, and submits the paired PRs.

The default one-machine adoption remains supported.

## Architecture and ownership

`geneset-extractor-dev` owns the workspace identity, handoff package,
workspace-local helpers, staged verification records, documentation, and safe
submission gating.  `dig-gene-set-extractors` continues to own source-data
processing, statistical analysis, mapping, ranking, gene-set construction,
converters, and reusable smoke fixtures.  The initial implementation requires
no competing DIG handoff framework.

## Additive contract

Add a versioned `adoption/handoff.json` to a portable handoff archive.  It
records a workspace identifier, library identifier, adoption mode, declared
remotes/branches, exact source revisions, source-inventory digest, and a list
of deliberately excluded paths.  The archive contains Git bundles plus a
safe source overlay so an uncommitted scaffold can be moved to the
reproduction host. It excludes `.git` directories, inputs, outputs, work directories,
receipts, caches, and large/generated biological artifacts.

The import command creates fresh clones from the bundles, restores only the
safe overlay, regenerates workspace-local helpers, and rewrites only the
host-specific `workspace.root`. A remote legacy root can be supplied at import
time. It is never copied implicitly to the reproduction host.

## Recommended commands: local authoring, remote reproduction

```bash
# On the local coding workstation. LEGACY_LOCAL contains read-only legacy
# code/configuration/reference GMTs; it need not contain full source inputs.
python3 -m submission_tools adopt \
  --existing "$LEGACY_LOCAL" --library-id MY_LIBRARY \
  --workspace "$LOCAL_WORKSPACE" --github-user USERNAME \
  --smoke-inputs "$SMALL_REDISRIBUTABLE_FIXTURES" \
  --ai-mode authoring
cd "$LOCAL_WORKSPACE"
codex
./verify-adoption --stage authoring

# Transfer the reviewed authoring state to the remote/HPC reproduction host.
python3 -m submission_tools export-adoption \
  --workspace "$LOCAL_WORKSPACE" --output reproduction-handoff.tar.gz

# On the remote/HPC host. LEGACY_REMOTE may use a different absolute path.
python3 -m submission_tools import-adoption \
  --bundle reproduction-handoff.tar.gz --workspace "$REMOTE_FULL_WORKSPACE" \
  --legacy-root "$LEGACY_REMOTE" --ai-mode full
```

`--smoke-inputs` is mandatory in authoring mode. It copies only the user's
small, redistributable smoke fixture into the isolated wrapper and records its
checksum. The fixture must be sufficient to exercise the intended workflow and
produce at least one deterministic gene set. Codex evaluates that fixture but
must not download, discover, generate, or silently substitute local data. If
it is inadequate, Codex reports the exact fixture requirement to the user.

The reproduction host explicitly obtains full inputs and launches the full run.
For example, it may use the generated native or Apptainer cluster adapter;
the tools never submit scheduler jobs merely because a handoff was imported.
It then runs `./verify-adoption --stage full --work-dir work-full` followed by
`./submit-adoption` after a passing full receipt.

## Verification semantics

`--stage authoring` performs static wrapper/DIG validation, lightweight
wrapper tests, the declared smoke command, smoke outputs, and smoke
provenance.  It does not compare full legacy outputs and cannot authorize
`submit-adoption`.

The existing default (`--stage all`) stays backward compatible.  `--stage
full` validates declared full output mappings and full provenance without
running a download command implicitly.  A successful full verification record
is tied to the current workspace digest, code commits, and selected work
directory.  `submit-adoption` rejects authoring-only verification.

## Safety and evidence

Handoffs are a code/configuration transport, not a dataset transport.  They
must not include secrets, credentials, full inputs, generated outputs, or
home-directory paths.  Full receipts record commands, revisions, manifests,
and result digests but do not claim cryptographic proof of reproducibility.
The final remote workspace remains the only location that can validate a full
run and submit it.

## Remote input contract

During local authoring, the agent completes the committed
`reproduction/input_manifest.tsv` with every required full input's stable
identifier, release, checksum when feasible, access method, and workflow
stage. `export-adoption` derives two handoff-only aids from that manifest:

```text
handoff/remote_input_requirements.md
handoff/remote_input_bindings.template.yaml
```

The remote operator copies the template outside the workspace and supplies the
actual authorized locations, for example:

```yaml
schema_version: "1.0"
library_id: MY_LIBRARY
mode: full
inputs:
  expression_matrix:
    path: /secure/project/MY_LIBRARY/expression_matrix.tsv.gz
```

This runtime-only binding file is never committed or handed off. Validation
requires one binding for every non-fixture full input, checks file existence
and declared SHA-256 values, and permits `download: true` only for inputs whose
manifest access method is public download. It records only a binding digest and
validation outcome in the receipt, never remote absolute paths or credentials.

## Advanced reverse handoff

If legacy code and reference GMTs are available only on the remote host, an
authoring handoff may still be exported remotely and imported on the local
machine. That is an advanced exception; the recommended workflow creates the
adoption workspace locally and transfers only one reviewed code handoff to the
remote reproduction host.

## Tests and rollout

1. Add archive round-trip tests using only temporary local Git repositories.
2. Add authoring-stage tests proving it skips full comparisons and cannot
   submit.
3. Add imported-workspace tests with different absolute roots and an optional
   remote legacy root.
4. Add full-stage/receipt submission-gate tests.
5. Document the remote/HPC workflow and retain the current one-machine
   tutorial unchanged as the default path.

The first implementation layer delivers the handoff archive, import/export,
authoring-stage verification, and documentation.  Scheduler resource profiles
and automated remote reconciliation remain later, optional work.
