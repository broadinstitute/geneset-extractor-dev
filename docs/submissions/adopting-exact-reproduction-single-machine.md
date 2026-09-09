# Exact reproduction: single machine

Use this only when one machine can safely hold full inputs and execute the
complete workflow.

```bash
export LIBRARY_ID="MY_LIBRARY"
export GITHUB_USER="USERNAME"
export LEGACY="/absolute/path/to/existing_submission"
export WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID"
export WORK_DIR="$WORKSPACE/work-full"

git clone --branch main https://github.com/broadinstitute/geneset-extractor-dev.git submission-system-tools
cd submission-system-tools
python3 -m submission_tools adopt \
  --existing "$LEGACY" --library-id "$LIBRARY_ID" \
  --workspace "$WORKSPACE" --github-user "$GITHUB_USER"
cd "$WORKSPACE"
codex
```

Tell Codex:

```text
Follow AI_ADOPTION_PROMPT.md completely.

This is an exact_reproduction adoption. Preserve scientific behavior, declare
every input, run full reproduction, and map every authoritative legacy GMT to
its full regenerated counterpart with set_equivalent comparison. Keep full
inputs and outputs untracked and keep substantive logic in DIG.
```

Then:

```bash
cd "$WORKSPACE/geneset-extractor-dev"
cat ../adoption/gitignore_allowlist.md >> .gitignore
cd "$WORKSPACE"
./verify-adoption --work-dir "$WORK_DIR"
./submit-adoption --yes
```

Submit only after full comparison and provenance pass.
