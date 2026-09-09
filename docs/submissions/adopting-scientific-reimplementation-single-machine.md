# Scientific reimplementation: single machine

Use this when one machine can run the full workflow but historical data or
method details prevent an exact reproduction.

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

This is a scientific_reimplementation adoption. Treat the legacy implementation
as scientific evidence, recreate substantive logic in DIG, and keep the wrapper
thin. Complete adoption/source_assessment.md, source-version fields for every
full input, scientific_comparability mappings, justified metrics, and required
set-name mappings. Run the full workflow and do not claim set equivalence.
```

Then:

```bash
cd "$WORKSPACE/geneset-extractor-dev"
cat ../adoption/gitignore_allowlist.md >> .gitignore
cd "$WORKSPACE"
./verify-adoption --work-dir "$WORK_DIR"
./submit-adoption --yes
```

A ready submission also requires an approved scientific-review reference in
`submission.yaml`. Keep inputs, generated artifacts, receipts, and bindings
out of Git.
