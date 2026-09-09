# Scientific reimplementation: local authoring → remote full reproduction

Use this recommended path when historical releases or implementation details
cannot support exact reproduction. The final claim is scientific comparability,
not set equivalence.

## Local authoring machine

```bash
export LIBRARY_ID="MY_LIBRARY"
export GITHUB_USER="USERNAME"
export LEGACY_LOCAL="/local/path/to/legacy_evidence"
export LOCAL_WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID-authoring"
export SMOKE_INPUTS="/local/path/to/small_redistributable_fixtures"

git clone --branch main https://github.com/broadinstitute/geneset-extractor-dev.git submission-system-tools
cd submission-system-tools
python3 -m submission_tools adopt \
  --existing "$LEGACY_LOCAL" --library-id "$LIBRARY_ID" \
  --workspace "$LOCAL_WORKSPACE" --github-user "$GITHUB_USER" \
  --smoke-inputs "$SMOKE_INPUTS" --ai-mode authoring
cd "$LOCAL_WORKSPACE"
codex
```

Tell Codex:

```text
Follow AI_ADOPTION_PROMPT.md completely.

This is a scientific_reimplementation adoption. Treat legacy code and GMTs as
read-only scientific evidence; recreate substantive processing in DIG and keep
the wrapper thin. Complete adoption/source_assessment.md and input_manifest.tsv
with source_version_confidence and legacy_input_relationship for every full
input. Declare scientific_comparability mappings, justified metrics, and any
set-name mapping. Use only smoke fixtures locally; do not download full inputs
or claim exact reproduction.
```

```bash
./verify-adoption --stage authoring
python3 -m submission_tools export-adoption \
  --workspace "$LOCAL_WORKSPACE" --output reproduction-handoff.tar.gz
# Transfer reproduction-handoff.tar.gz to the remote/HPC machine.
```

## Remote/HPC reproduction machine

```bash
export LIBRARY_ID="MY_LIBRARY"
export LEGACY_REMOTE="/remote/path/to/authoritative_legacy_submission"
export REMOTE_WORKSPACE="$HOME/gene-set-adoptions/$LIBRARY_ID-full"
export REMOTE_BINDINGS="/secure/project/$LIBRARY_ID/input-bindings.yaml"

python3 -m submission_tools import-adoption \
  --bundle reproduction-handoff.tar.gz --workspace "$REMOTE_WORKSPACE" \
  --legacy-root "$LEGACY_REMOTE" --ai-mode full
less "$REMOTE_WORKSPACE/adoption/remote_input_requirements.md"
cp "$REMOTE_WORKSPACE/adoption/remote_input_bindings.template.yaml" "$REMOTE_BINDINGS"
# Edit $REMOTE_BINDINGS with authorized full-input paths.

cd "$REMOTE_WORKSPACE/geneset-extractor-dev"
cat ../adoption/gitignore_allowlist.md >> .gitignore
cd "$REMOTE_WORKSPACE/geneset-extractor-dev/$LIBRARY_ID"
SUBMISSION_WORK_DIR="$REMOTE_WORKSPACE/work-full" bash reproduction/reproduce.sh full
cd "$REMOTE_WORKSPACE"
./verify-adoption --stage full --work-dir work-full --input-bindings "$REMOTE_BINDINGS"
./submit-adoption --yes
```

Before marking ready, add the required approved scientific-review reference to
`submission.yaml`. Do not commit inputs, artifacts, receipts, or bindings.
