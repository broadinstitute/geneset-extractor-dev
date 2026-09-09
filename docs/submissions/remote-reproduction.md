# Remote authoring and full reproduction

Use this optional workflow when the machine running Codex should create code
and run only tiny fixtures, while a remote/HPC machine should obtain full
inputs and perform expensive reproduction. The normal one-machine adoption
workflow remains the default.

**All substantive data processing and gene-set generation logic belongs in
`dig-gene-set-extractors`. `geneset-extractor-dev` may configure, dispatch,
execute, refresh, and publish that logic, but must not independently implement
it.**

## 1. Create the source workspace on the remote host

The remote host must be able to read the legacy directory. Create an isolated
workspace with an authoring-only prompt:

```bash
python3 -m submission_tools adopt \
  --existing "$LEGACY" --library-id MY_LIBRARY \
  --workspace "$REMOTE_WORKSPACE" --github-user USERNAME \
  --ai-mode authoring
python3 -m submission_tools export-adoption \
  --workspace "$REMOTE_WORKSPACE" --output "$HOME/authoring-handoff.tar.gz"
```

Transfer the archive to the coding workstation with an approved transport.
It contains source code, configuration, adoption inventory/reference metadata,
and Git history only. It excludes `.git` worktrees, inputs, outputs, `work/`,
receipts, and caches.

## 2. Author locally with Codex

```bash
python3 -m submission_tools import-adoption \
  --bundle authoring-handoff.tar.gz --workspace "$LOCAL_WORKSPACE" \
  --ai-mode authoring
cd "$LOCAL_WORKSPACE"
codex
```

Tell Codex to follow `AI_ADOPTION_PROMPT.md`. Authoring mode permits DIG code,
thin wrapper/configuration work, and tiny redistributable fixtures only. Do
not download full datasets, run full reproduction, submit scheduler jobs, or
claim full equivalence locally.

```bash
./verify-adoption --stage authoring
python3 -m submission_tools export-adoption \
  --workspace "$LOCAL_WORKSPACE" --output reproduction-handoff.tar.gz
```

Authoring verification cannot authorize submission. Commit and push reviewed
`adopt/MY_LIBRARY` branches before the final handoff.

## 3. Reproduce and submit remotely

Import the reviewed handoff into a fresh remote workspace and give it the
unchanged legacy root available on that host:

```bash
python3 -m submission_tools import-adoption \
  --bundle reproduction-handoff.tar.gz \
  --workspace "$REMOTE_FULL_WORKSPACE" --legacy-root "$LEGACY" \
  --ai-mode full

cd "$REMOTE_FULL_WORKSPACE/geneset-extractor-dev/MY_LIBRARY"
SUBMISSION_WORK_DIR="$REMOTE_FULL_WORKSPACE/work-full" \
  bash reproduction/reproduce.sh full
cd "$REMOTE_FULL_WORKSPACE"
./verify-adoption --stage full --work-dir work-full
./submit-adoption --yes
```

For a larger library, use the generated per-library native or Apptainer
cluster adapter explicitly. The tooling never calls `qsub` or downloads data
on its own. Full outputs and receipts remain untracked artifacts on the
remote host; the full receipt records revisions, manifests, command, selected
work directory, and validation outcome but is not cryptographic proof.
