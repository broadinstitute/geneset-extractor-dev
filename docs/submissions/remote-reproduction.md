# Local authoring and remote full reproduction

This is the technical reference for the local-authoring → remote-full-
reproduction path. For the complete copyable procedure, including the Codex
instruction and final submission gate, use the
[trusted-adoption tutorial](adopting-trusted-existing-submission.md#short-version-local-authoring--remote-full-reproduction).

**All substantive data processing and gene-set generation logic belongs in
`dig-gene-set-extractors`. `geneset-extractor-dev` may configure, dispatch,
execute, refresh, and publish that logic, but must not independently implement
it.**

## 1. Create the authoring workspace locally

The local machine needs a read-only copy of legacy code, configuration, and
reference GMT evidence. It does not need the complete source datasets. Create
an isolated workspace with an authoring-only prompt:

```bash
python3 -m submission_tools adopt \
  --existing "$LEGACY_LOCAL" --library-id MY_LIBRARY \
  --workspace "$LOCAL_WORKSPACE" --github-user USERNAME \
  --smoke-inputs "$SMALL_REDISRIBUTABLE_FIXTURES" \
  --ai-mode authoring
cd "$LOCAL_WORKSPACE"
codex
```

Tell Codex to follow `AI_ADOPTION_PROMPT.md`. Authoring mode permits DIG code,
thin wrapper/configuration work, and tiny redistributable fixtures only. Do
not download full datasets, run full reproduction, submit scheduler jobs, or
claim full equivalence locally.

`--smoke-inputs` is optional but recommended: it copies a user-selected small
redistributable file or directory into `tests/fixtures/user_supplied/`, records
checksums in the committed input manifest, and rejects files larger than
10 MiB. Do not pass full source data to this option.

```bash
./verify-adoption --stage authoring
```

Authoring verification cannot authorize submission. The later handoff retains
safe uncommitted source/configuration overlays as well as Git history, so a
local push is not required before remote full reproduction.

## 2. Hand off reviewed code to the remote host

After small-scale validation, create a code-only archive and transfer it to
the remote host with an approved mechanism such as `scp` or `rsync`:

```bash
python3 -m submission_tools export-adoption \
  --workspace "$LOCAL_WORKSPACE" --output reproduction-handoff.tar.gz
```

The archive contains source code, configuration, adoption inventory/reference
metadata, and Git history. It excludes `.git` worktrees, inputs, outputs,
`work/`, receipts, and caches.

## 3. Reproduce and submit remotely

Import the reviewed handoff into a fresh remote workspace and give it the
unchanged legacy root available on that host:

```bash
python3 -m submission_tools import-adoption \
  --bundle reproduction-handoff.tar.gz \
  --workspace "$REMOTE_FULL_WORKSPACE" --legacy-root "$LEGACY_REMOTE" \
  --ai-mode full

# Read requirements generated from the committed input manifest, then copy the
# placeholder file outside Git and replace each path with an authorized file.
less "$REMOTE_FULL_WORKSPACE/adoption/remote_input_requirements.md"
cp "$REMOTE_FULL_WORKSPACE/adoption/remote_input_bindings.template.yaml" \
  /secure/project/MY_LIBRARY/input-bindings.yaml
# Edit /secure/project/MY_LIBRARY/input-bindings.yaml

cd "$REMOTE_FULL_WORKSPACE/geneset-extractor-dev/MY_LIBRARY"
SUBMISSION_WORK_DIR="$REMOTE_FULL_WORKSPACE/work-full" \
  bash reproduction/reproduce.sh full
cd "$REMOTE_FULL_WORKSPACE"
./verify-adoption --stage full --work-dir work-full \
  --input-bindings /secure/project/MY_LIBRARY/input-bindings.yaml
./submit-adoption --yes
```

For a larger library, use the generated per-library native or Apptainer
cluster adapter explicitly. The tooling never calls `qsub` or downloads data
on its own. Full outputs and receipts remain untracked artifacts on the
remote host; the full receipt records revisions, manifests, command, selected
work directory, and validation outcome but is not cryptographic proof.
The binding file is runtime-only: it maps committed logical `input_id` values
to authorized remote files, is never committed or included in a handoff, and
must not contain credentials or signed URLs.

## Advanced reverse handoff

If the legacy source and reference outputs are available only on the remote
host, it remains valid to create an authoring handoff remotely and import it
locally. That reverse direction is an exception; local authoring followed by
one remote handoff is the recommended workflow.
