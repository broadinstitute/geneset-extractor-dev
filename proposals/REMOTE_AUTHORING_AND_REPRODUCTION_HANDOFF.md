# Remote authoring and reproduction handoff

## Purpose

An adoption may require a full source-data reproduction that is inappropriate
for the machine used by an interactive coding agent.  This proposal separates
the two roles without weakening the existing adoption contract:

* an **authoring host** creates DIG and thin-wrapper code, configuration, and
  small deterministic fixtures;
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
safe source overlay so an uncommitted scaffold can be moved to the authoring
host.  It excludes `.git` directories, inputs, outputs, work directories,
receipts, caches, and large/generated biological artifacts.

The import command creates fresh clones from the bundles, restores only the
safe overlay, regenerates workspace-local helpers, and rewrites only the
host-specific `workspace.root`.  A remote legacy root can be supplied at
import time.  It is never copied implicitly to the authoring host.

## Commands

```bash
# On the host that can read the legacy material.
python3 -m submission_tools export-adoption \
  --workspace "$REMOTE_WORKSPACE" --output authoring-handoff.tar.gz

# On the coding workstation.
python3 -m submission_tools import-adoption \
  --bundle authoring-handoff.tar.gz --workspace "$LOCAL_WORKSPACE"
cd "$LOCAL_WORKSPACE"
codex
./verify-adoption --stage authoring

# Export the reviewed authoring state, transfer it to the reproduction host,
# then create a fresh remote workspace from it.
python3 -m submission_tools export-adoption \
  --workspace "$LOCAL_WORKSPACE" --output reproduction-handoff.tar.gz
python3 -m submission_tools import-adoption \
  --bundle reproduction-handoff.tar.gz --workspace "$REMOTE_FULL_WORKSPACE" \
  --legacy-root "$LEGACY"
```

The reproduction host explicitly downloads inputs and launches the full run.
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
