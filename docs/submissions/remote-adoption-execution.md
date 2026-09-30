# Local authoring and remote adoption execution

Use this workflow when Codex authors a library extension on a local machine while
full input data and cluster capacity live on a remote system. Git branches carry
source code and configuration; full inputs, generated outputs, and work
directories remain on the remote system.

## 1. Author locally

Create the isolated adoption workspace on the Codex machine, use the generated
`AI_ADOPTION_PROMPT.md`, and run only lightweight smoke checks there. Do not
copy full source datasets into either repository.

When the branch is ready for remote testing, publish it without opening a PR:

```bash
cd "$AUTHORING_WORKSPACE"
./submit-adoption --yes --push-only
```

For maintainer workspaces whose `origin` is canonical, add:

```bash
./submit-adoption --yes --push-only --allow-upstream-origin
```

This command performs safe staging, pins the wrapper to the pushed DIG commit,
and pushes only the recorded `adopt/...` branches. It never invokes `gh`, opens
a PR, runs download scripts, or claims full verification passed.

Export the small handoff archive once:

```bash
python3 -m submission_tools export-adoption-handoff \
  --workspace "$AUTHORING_WORKSPACE" \
  --output "$(basename "$AUTHORING_WORKSPACE")-handoff.tar.gz"
```

The archive contains adoption metadata and inventory/reference information, not
raw inputs, generated outputs, work directories, or repository clones.

## 2. Initialize the remote execution workspace

Transfer the handoff archive to the remote system. The remote system must have
a read-only copy of the legacy code/configuration and authoritative GMTs at
`$LEGACY_REMOTE`, plus access to the full source inputs.

```bash
python3 -m submission_tools init-remote-adoption \
  --handoff GTEx-hz-consensus-handoff.tar.gz \
  --workspace "$REMOTE_WORKSPACE" \
  --legacy "$LEGACY_REMOTE"
```

This clones the recorded `adopt/...` branches, verifies the remote legacy
reference against inventory checksums, and creates remote-local helpers. It
records remote paths in the remote workspace manifest; do not edit the
authoring manifest by hand.

## 3. Run full reproduction remotely

Keep artifacts outside both repository clones:

```bash
cd "$REMOTE_WORKSPACE"
export SUBMISSION_WORK_DIR="$REMOTE_WORKSPACE/work-full"

# Run the library's documented full reproduction or cluster launcher here.
```

Use the library-specific Apptainer/native cluster launcher and its documented
resource options when appropriate. Never commit `inputs/`, `outputs/`, `work/`,
or run receipts.

## 4. Iterate through Git

After a local code fix, rerun local `--push-only`. On the remote system:

```bash
cd "$REMOTE_WORKSPACE"
./sync-adoption-workspace
```

The sync helper fast-forwards only the recorded work branches, refuses
remote-side source changes, retains remote work artifacts, and confirms that
the wrapper's `dig.commit` matches the checked-out DIG revision.

## 5. Verify and create PRs only after success

After full reproduction and all mapped comparisons complete:

```bash
cd "$REMOTE_WORKSPACE"
./verify-adoption --work-dir work-full
./submit-adoption --yes
```

Use `--allow-upstream-origin` again for maintainer-mode workspaces. The final
command requires current full verification and then opens or reuses draft PRs;
it never merges them.
